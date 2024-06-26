from channels.generic.websocket import AsyncWebsocketConsumer
from .auth.jwt import validate_jwt_and_get_user_id
import json
# import re
from django.contrib.auth.models import User

import requests
from notifications import settings
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.http import JsonResponse
from enum import Enum

from .models import Room

class NotificationType(Enum):
    SENT = 1
    ACCEPTED = 2
    REJECTED = 3
    REMOVED = 4
    NAME_CHANGED = 5
    IMG_CHANGED = 6
    USER_ONLINE = 7
    USER_OFFLINE = 8
    USER_ONLINE_NOTIFICATION = 9
    USER_OFFLINE_NOTIFICATION = 10
    GAME_FOUND = 11
    GAME_INVITE = 12



class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        #Get the token from the query string
        query_string = self.scope["query_string"]
        query_params = query_string.decode()
        query_dict = parse_qs(query_params)
        try:
            jwt_token = query_dict["token"][0]
        except:
            await self.close()
            return JsonResponse({"detail": "No token provider."}, status=400)

        # Find the user from the token in the database
        user_id = await validate_jwt_and_get_user_id(jwt_token)
        if not user_id:
            await self.close()
            return JsonResponse({"detail": "Bad token provided."}, status=400)

        # user = User.objects.get(pk=user_id)

        user = await database_sync_to_async(User.objects.get)(pk=user_id)
        self.id = user_id
        self.username = user.username

        # Create a group named "group_<user_id>"
        await self.channel_layer.group_add(
            f'group_{self.id}',
            self.channel_name
        )

        # Create a group for global notifications
        await self.channel_layer.group_add(
            f'broadcast',
            self.channel_name
        )

        #If room does not exist, create it and set connections to 1
        # If room exists, increment connections by 1
        try:
            room = await database_sync_to_async(Room.objects.get)(name="global")
            room.connections += 1
            await database_sync_to_async(room.save)()
        except Room.DoesNotExist:
            room = await database_sync_to_async(Room.objects.create)(name="global", connections=1)


        # Send a message to your friends that you are online
        headers = {
            "Authorization": f"Bearer {jwt_token}"
        }
        self.headers = headers
        body = {"is_online": True}
        requests.put(settings.USERS_SERVICE_HOST_INTERNAL + "/users/status/",json=body, headers=headers, verify=False)
        friends = requests.get(settings.USERS_SERVICE_HOST_INTERNAL + f"/friends/", headers=headers, verify=False).json()["users"]

        for friend in friends:
            await self.channel_layer.group_send(
                f'group_{friend["id"]}',
                {
                    'type': 'send_message',
                    'message': {
                        "message": f'{self.username} is online',
                        "ntype": NotificationType.USER_ONLINE_NOTIFICATION.value,
                        "sender": {
                            "id": self.id,
                            "username": self.username
                        },
                    }
                }
            )
        await self.channel_layer.group_send(
            'broadcast',
            {
                'type': 'send_message',
                'message': {
                    "ntype": NotificationType.USER_ONLINE.value,
                    "sender": {
                        "id": self.id,
                        "username": self.username
                    },
                },
            }
        )

        await self.accept()

    async def disconnect(self, code):
        try:

            # Check room connections
            room = await database_sync_to_async(Room.objects.get)(name="global")
            room.connections -= 1
            if room.connections == 0:
                await database_sync_to_async(room.delete)()
            else:
                await database_sync_to_async(room.save)()
                return


            headers = {
                "Authorization": settings.MICROSERVICE_API_TOKEN
            }

            body = {"is_online": False, "user_id": self.id}
            requests.put(settings.USERS_SERVICE_HOST_INTERNAL + "/users/status/",json=body, headers=headers, verify=False)
            friends = requests.get(settings.USERS_SERVICE_HOST_INTERNAL + f"/friends/{str(self.id)}/",  headers=headers, verify=False)

            if friends.status_code == 200:
                friends = friends.json()["users"]
            else:
                friends = []


            await self.channel_layer.group_send(
                'broadcast',
                {
                    'type': 'send_message',
                    'message': {
                        "ntype": NotificationType.USER_OFFLINE.value,
                        "sender": {
                            "id": self.id,
                            "username": self.username
                        },
                    },
                }
            )
            for friend in friends:
                await self.channel_layer.group_send(
                    f'group_{friend["id"]}',
                    {
                        'type': 'send_message',
                        'message': {
                            "ntype": NotificationType.USER_OFFLINE_NOTIFICATION.value,
                            "message": f'{self.username} is offline'
                        }
                    }
                )
            self.channel_layer.group_discard(
                f'group_{self.id}',
                self.channel_name
            )

            # Leave the any queues or tournaments
            body = {"user_id": self.id}
            requests.post(settings.MATCHMAKING_SERVICE_HOST_INTERNAL + "/queue/leave/", headers=headers, json=body, verify=False)

            requests.post(settings.MATCHMAKING_SERVICE_HOST_INTERNAL + "/tournament/leave/", headers=headers, json=body, verify=False)
        except Exception as e:
            print(e)
        


    async def send_message(self, event):


        # Send message to WebSocket
        await self.send(text_data=json.dumps(event))
