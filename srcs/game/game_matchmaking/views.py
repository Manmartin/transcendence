from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view
from functools import wraps
from django.utils.decorators import method_decorator
from django.shortcuts import get_object_or_404
import random
import requests

from .notifications.send_notification import send_friend_request_notification, send_tournament_players_update_notification
from .notifications.constants import NotificationType

from rest_framework.views import APIView

from django.db.models import Q
from .models import Game, GameInvite, Tournament, UserTournament
from django.contrib.auth.models import User

from django.conf import settings

def private_microservice_endpoint(f):
    @wraps(f)
    def decorated_function(request, *args, **kwargs):
        api_token = request.headers.get('Authorization')
        if not api_token or api_token != settings.MICROSERVICE_API_TOKEN:
            return JsonResponse({'detail': 'Invalid API token.'}, status=401)
        return f(request, *args, **kwargs)
    return decorated_function


'''
Create a new game

Parameters:
    - playerLeft (Required): The id of the playerLeft
    - playerRight (Required): The id of the playerRight

'''
@api_view(['POST'])
@private_microservice_endpoint
def create_game(request):
    playerLeft = request.data.get('playerLeft')
    playerRight = request.data.get('playerRight')

    if playerLeft is None or playerLeft == '' or playerRight is None or playerRight == '':
        return JsonResponse({'error': 'playerLeft and playerRight are required'}, status=400)

    try:
        playerLeftObj = User.objects.get(id=playerLeft)
        playerRightObj = User.objects.get(id=playerRight)

        # Check if a Game already exists for the user and are waiting, IN_PROGRESS or PAUSED
        game = Game.objects.filter(Q(playerLeft=playerLeftObj) | Q(playerRight=playerLeftObj)).filter(Q(status=Game.GameStatus.WAITING) | Q(status=Game.GameStatus.IN_PROGRESS) | Q(status=Game.GameStatus.PAUSED))
        if game.exists():
            return JsonResponse({'error': 'game already exists'}, status=409)
        game = Game.objects.filter(Q(playerLeft=playerRightObj) | Q(playerRight=playerRightObj)).filter(Q(status=Game.GameStatus.WAITING) | Q(status=Game.GameStatus.IN_PROGRESS) | Q(status=Game.GameStatus.PAUSED))
        if game.exists():
            return JsonResponse({'error': 'game already exists'}, status=409)
    except User.DoesNotExist:
        return JsonResponse({'error': 'player does not exist'}, status=404)
    except:
        return JsonResponse({'error': 'error while querying the database'}, status=500)

    game = Game.objects.create(playerLeft=playerLeftObj, playerRight=playerRightObj)
    game.save()

    return JsonResponse({'game_id': game.id}, status=201)

'''
Get all the games of the logged in user

The user must be authenticated to get the games

Parameters:
    - status (Optional): Filter the games by status (WAITING, IN_PROGRESS, PAUSED)
    - opponent (Optional): Filter the games by the opponent's username

'''
@api_view(['GET'])
def get_user_games(request, id):
    user = get_object_or_404(User, id=id)

    if not user or user is None:
        return JsonResponse({'error': 'user is required'}, status=400)

    #Check if the url has a query parameter for the status of the game
    gameStatus = request.query_params.get('status')
    # Check if the url has a query parameter for the opponent's username
    opponent = request.query_params.get('opponent')

    opponentObj = None

    # Get the opponent's object
    if opponent:
        try:
            opponentObj = User.objects.get(username=opponent)
        except User.DoesNotExist:
            return JsonResponse({'error': 'opponent does not exist'}, status=404)
        except:
            return JsonResponse({'error': 'error while querying the database'}, status=500)
    try:
        games = Game.objects.filter(Q(playerLeft=user) | Q(playerRight=user))
        if gameStatus:
            games = games.filter(status=gameStatus)
        if opponent and opponentObj is not None:
            games = games.filter(Q(playerLeft=opponentObj) | Q(playerRight=opponentObj))
    except Game.DoesNotExist:
        return JsonResponse({'error': 'no games found'}, status=404)
    except Exception as e:
        print(e)
        return JsonResponse({'error': 'error while querying the database'}, status=500)

    gamesList = []
    for game in games:
        gamesList.append({
            'id': game.id,
            'playerLeft': game.playerLeft.username,
            'playerRight': game.playerRight.username,
            'playerLeftId': game.playerLeft.id,
            'playerRightId': game.playerRight.id,
            'playerLeftScore': game.playerLeftScore,
            'playerRightScore': game.playerRightScore,
            'winner': game.winner.id if game.winner is not None else None,
            'winnerId': game.winner.id if game.winner is not None else None,
            'tournament': game.tournament.id if game.tournament is not None else None,
            'status': game.status
        })
    return JsonResponse({'detail': gamesList}, status=200)


@method_decorator(never_cache, name='dispatch')
class GameChallengeView(APIView):

    '''
    Create a new game challenge

    Check if the user already has a game waiting, in progress or paused

    Check if the opponent exists and if the user has already sent an invite for the opponent

    Parameters:
        - opponent (Required): The id of the opponent
    '''
    def post(self,request):
        opponent = request.data.get('opponent')

        if opponent is None or opponent == '':
            return JsonResponse({'error': 'opponent is required'}, status=400)

        # Check if a Game already exists for the user and are waiting, IN_PROGRESS or PAUSED
        try:
            game = Game.objects.filter(Q(playerLeft=request.user) | Q(playerRight=request.user)).filter(Q(status=Game.GameStatus.WAITING) | Q(status=Game.GameStatus.IN_PROGRESS) | Q(status=Game.GameStatus.PAUSED))
            if game.exists():
                return JsonResponse({'error': 'game already exists'}, status=409)
        except Exception as e:
            print(e)
            return JsonResponse({'error': 'error while querying the database'}, status=500)

        try:
            opponentObj = User.objects.get(id=opponent)
        except User.DoesNotExist:
            print('opponent does not exist')
            return JsonResponse({'error': 'opponent does not exist'}, status=404)
        except Exception as e:
            print(e)
            return JsonResponse({'error': 'error while querying the database'}, status=500)

        try:
            oldInvite = GameInvite.objects.filter(sender=request.user, receiver=opponentObj).filter(status=GameInvite.InviteStatus.PENDING)
            if oldInvite.exists():
                return JsonResponse({'error': 'invite already sent'}, status=409)
            invite = GameInvite.objects.create(game=None, sender=request.user, receiver=opponentObj)
            invite.save()
        except Exception as e:
            print(e)
            return JsonResponse({'error': 'error while creating the invite'}, status=500)

        try:
            send_friend_request_notification(request.user, opponentObj, NotificationType.CHALLENGE)
        except Exception as e:
            print(e)
            print('Error while sending notification')

        return JsonResponse({'invite_id': invite.id}, status=201)

    '''
    Get all the game challenges of the logged in user

    The user must be authenticated to get the game challenges

    Parameters:
        - status (Optional): Filter the game challenges by status (PENDING, ACCEPTED, DECLINED)
        - opponent (Optional): Filter the game challenges by the opponent's username
    '''
    def get(self, request):
        user = request.user

        if not user or user is None:
            return JsonResponse({'error': 'user is required'}, status=400)

        inviteStatus = request.query_params.get('status')
        opponent = request.query_params.get('opponent')

        try:
            invites = GameInvite.objects.filter(receiver=user)
            if opponent:
                opponentObj = User.objects.get(username=opponent)
                invites = GameInvite.objects.filter(receiver=opponentObj, sender=user)
            if inviteStatus:
                invites = invites.filter(status=inviteStatus)
        except GameInvite.DoesNotExist:
            return JsonResponse({'error': 'no invites found'}, status=404)
        except:
            return JsonResponse({'error': 'error while querying the database'}, status=500)

        invitesList = []
        for invite in invites:
            invitesList.append({
                'id': invite.id,
                'sender': invite.sender.username,
                'receiver': invite.receiver.username,
                'status': invite.status
            })
        print(invitesList)
        return JsonResponse({'detail': invitesList}, status=200)

@method_decorator(never_cache, name='dispatch')
class GameTournamentView(APIView):

    '''
    Create a new tournament

    Check if the players exist and if they are already in a tournament

    This call can only be made by the microservice MATCHMAKING

    Parameters:
        - players (Required): A list of players' ids
    '''
    @method_decorator(private_microservice_endpoint)
    def post(self, request):
        data = request.data["players"]
        players = []
        tournament = None
        initia_game = None

        for player in data:
            try:
                current = User.objects.get(id=player['id'])
                hasTournament = UserTournament.objects.filter(user=current,
                                                              tournament__tournament_winner=None,
                                                              tournament__status__in=[Tournament.TournamentStatus.WAITING, Tournament.TournamentStatus.IN_PROGRESS]).exists()
                if hasTournament:
                    return JsonResponse({'error': 'user already in a tournament'}, status=409)

                if player not in players:
                    players.append(current)
                else:
                    return JsonResponse({'error': 'duplicate players'}, status=400)
            except Exception as e:
                print(e)
                return JsonResponse({'error': 'player does not exist'}, status=404)
        
        try:
            tournament = Tournament.objects.create()

            tournament.save()

            for player in players:
                userTournament = UserTournament.objects.create(user=player, tournament=tournament)
                userTournament.save()

            players.sort(key=lambda x: x.id)

            initia_game = Game.objects.create(playerLeft=players[0], playerRight=players[1], tournament=tournament)
            initia_game.save()

        except Exception as e:
            print(e)
            if tournament is not None:
                tournament.delete()
            if initia_game is not None:
                initia_game.delete()
            return JsonResponse({'error': 'error while creating the tournament'}, status=500)
        
        return JsonResponse({'tournament_id': tournament.id}, status=201)

    '''
    Get all the tournaments of the logged in user

    The user must be authenticated to get the tournaments
    '''
    def get(self, request):
        user = request.user

        if not user or user is None:
            return JsonResponse({'error': 'user is required'}, status=400)
        if not user.is_authenticated:
            return JsonResponse({'error': 'user is not authenticated'}, status=403)

        print("User: ", user, " is getting the tournaments")

        try:
            userTournaments = UserTournament.objects.filter(user=user).filter(status=UserTournament.UserStatus.PLAYING)
            tournaments = []
            for userTournament in userTournaments:
                tournaments.append({
                    'id': userTournament.tournament.id,
                    'status': userTournament.tournament.status
                })
            if len(tournaments) == 0:
                return JsonResponse({'error': 'no tournaments found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': 'error while querying the database'}, status=500)

        return JsonResponse({'detail': tournaments}, status=200)
    
    def get_object(self, id):
        try:
            return Tournament.objects.get(id=id)
        except Tournament.DoesNotExist:
            return JsonResponse({'error': 'tournament does not exist'}, status=404)
        except:
            return JsonResponse({'error': 'error while querying the database'}, status=500)
        
        
'''
Get all the matches of a tournament

Parameters:
    - id (Required): The id of the tournament
'''
@never_cache
@api_view(['GET'])
def get_tournament_matches(request):
    tournament_id = request.query_params.get('id')

    if tournament_id is None or tournament_id == '':
        return JsonResponse({'error': 'tournament_id is required'}, status=400)

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return JsonResponse({'error': 'tournament does not exist'}, status=404)
    except:
        return JsonResponse({'error': 'error while querying the database'}, status=500)

    try:
        matches = Game.objects.filter(tournament=tournament)
    except Game.DoesNotExist:
        return JsonResponse({'error': 'no matches found'}, status=404)
    except:
        return JsonResponse({'error': 'error while querying the database'}, status=500)

    matchesList = []
    for match in matches:
        matchesList.append({
            'id': match.id,
            'playerLeft': match.playerLeft.username,
            'playerRight': match.playerRight.username,
            'playerLeftId': match.playerLeft.id,
            'playerRightId': match.playerRight.id,
            'playerLeftScore': match.playerLeftScore,
            'playerRightScore': match.playerRightScore,
            'status': match.status
        })
    return JsonResponse({'detail': matchesList}, status=200)

'''
Get all the players of a tournament

Parameters:
    - tournament_id (Required): The id of the tournament
'''
@never_cache
@api_view(['GET'])
def get_top_players(request):
    tournament_id = request.query_params.get('tournament_id')
    if tournament_id is None or tournament_id == '':
        return JsonResponse({'error': 'tournament_id is required'}, status=400)

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Exception as e:
        print(e)
        return JsonResponse({'error': 'error while querying the database'}, status=500)
    try:
        players = UserTournament.objects.filter(tournament=tournament)
        if players.exists():
            players_list = []
            for player in players:
                players_list.append({
                    'id': player.user.id,
                    'username': player.user.username
                })
            return JsonResponse({'players': players_list}, status=200)
    except Exception as e:
        print(e)
        return JsonResponse({'error': 'error while querying the database'}, status=500)
    return JsonResponse({'error': 'no players found'}, status=404)
    

@never_cache
@api_view(['POST'])
def next_tournament_game(request):
    tournament_id = request.data.get('tournament_id')
    tournament = None

    if tournament_id is None or tournament_id == '':
        return JsonResponse({'error': 'tournament_id is required'}, status=400)

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return JsonResponse({'error': 'tournament does not exist'}, status=404)
    except Exception as e:
        print("Error while querying the database: ", e)
        return JsonResponse({'error': 'error while querying the database'}, status=500)

    try:
        players_playing = UserTournament.objects.filter(tournament=tournament, status=UserTournament.UserStatus.PLAYING)
        players_playing_count = players_playing.count()
    except UserTournament.DoesNotExist:
        return JsonResponse({'error': 'no players found'}, status=404)
    except Exception as e:
        print("Error while querying the database for the players playing: ", e)
        return JsonResponse({'error': 'error while querying the database'}, status=500)
    
    if players_playing_count == 1:
        try:
            winner = players_playing.first().user
            tournament.tournament_winner = winner
            tournament.status = Tournament.TournamentStatus.FINISHED
            tournament.save()
            return JsonResponse({'winner': winner.username}, status=200)
        except Exception as e:
            print(e)
            return JsonResponse({'error': 'error while updating the tournament'}, status=500)
    
    if players_playing_count == 0:
        return JsonResponse({'error': 'No players playing'}, status=404)
    
    try:
        players_playing = players_playing.order_by('user__id')


        # Check if the game already exists
        game = Game.objects.filter(playerLeft=players_playing[0].user,
                                   playerRight=players_playing[1].user,
                                   tournament=tournament).filter(Q(status=Game.GameStatus.WAITING) | Q(status=Game.GameStatus.IN_PROGRESS) | Q(status=Game.GameStatus.PAUSED ))

        if game.exists():
            current_game = game.first()
            return JsonResponse({'game': {'id': current_game.id, 'status':
                                current_game.status, "playerLeft":
                                          current_game.playerLeft.username,
                                          "playerLeftId":
                                          current_game.playerLeft.id,
                                          "playerRight":
                                          current_game.playerRight.username,
                                          "playerRightId":
                                          current_game.playerRight.id}}, status=200)
        new_game = Game.objects.create(playerLeft=players_playing[0].user, playerRight=players_playing[1].user, tournament=tournament)
        new_game.save()

        current_game = new_game


        print("Sending notification")
        send_tournament_players_update_notification(tournament)

        return JsonResponse({'game': {'id': current_game.id, 'status': current_game.status, "playerLeft": current_game.playerLeft.username, "playerLeftId": current_game.playerLeft.id, "playerRight": current_game.playerRight.username, "playerRightId": current_game.playerRight.id}}, status=201)
            
    except Exception as e:
        print(e)
        return JsonResponse({'error': 'Error while creating the game'}, status=500)

@never_cache
@api_view(['GET'])
def user_tournament_status(request):
    user = request.user

    if not user or user is None or not user.is_authenticated:
        return JsonResponse({'error': 'user is required'}, status=403)

    tournament_id = request.query_params.get('tournament_id')

    if tournament_id is None or tournament_id == '':
        return JsonResponse({'error': 'tournament_id is required'}, status=400)

    try:
        tournament = Tournament.objects.get(id=tournament_id)
    except Tournament.DoesNotExist:
        return JsonResponse({'error': 'tournament does not exist'}, status=404)
    except:
        return JsonResponse({'error': 'error while querying the database'}, status=500)

    try:
        user_tournament = UserTournament.objects.get(user=user, tournament=tournament)
        return JsonResponse({'status': user_tournament.status}, status=200)
    except UserTournament.DoesNotExist:
        return JsonResponse({'error': 'user is not in the tournament'}, status=404)
    except:
        return JsonResponse({'error': 'error while querying the database'}, status=500)


@never_cache
@api_view(['POST'])
def accept_challenge(request):
    invite_id = request.data.get('invite_id')

    if invite_id is None or invite_id == '':
        return JsonResponse({'error': 'invite_id is required'}, status=400)

    try:
        invite = GameInvite.objects.get(id=invite_id)
    except GameInvite.DoesNotExist:
        return JsonResponse({'error': 'invite does not exist'}, status=404)
    except:
        return JsonResponse({'error': 'error while querying the database'}, status=500)

    if invite.status != GameInvite.InviteStatus.PENDING:
        return JsonResponse({'error': 'invite is not pending'}, status=400)

    invite.status = GameInvite.InviteStatus.ACCEPTED
    invite.save()

    game = Game.objects.create(playerLeft=invite.sender, playerRight=invite.receiver)
    game.save()

    invite.game = game
    invite.save()

    return JsonResponse({'game_id': game.id}, status=201)

@never_cache
@api_view(['POST'])
def decline_challenge(request):
    invite_id = request.data.get('invite_id')

    if invite_id is None or invite_id == '':
        return JsonResponse({'error': 'invite_id is required'}, status=400)

    try:
        invite = GameInvite.objects.get(id=invite_id)
    except GameInvite.DoesNotExist:
        return JsonResponse({'error': 'invite does not exist'}, status=404)
    except:
        return JsonResponse({'error': 'error while querying the database'}, status=500)

    if invite.status != GameInvite.InviteStatus.PENDING:
        return JsonResponse({'error': 'invite is not pending'}, status=400)

    invite.status = GameInvite.InviteStatus.DECLINED
    invite.save()

    return JsonResponse({'detail': 'invite declined'}, status=200)



