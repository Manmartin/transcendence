function extractOpponentFromResponse(response) {
  let opponent;
  if (response.playerLeft === Router.getUsername()) {
    opponent = response.playerRight;
  } else {
    opponent = response.playerLeft;
  }
  return opponent;
}

async function find1v1Game() {
  // Find any games on waiting status or paused status
  //
  
  if (Router.getJwt() === null) {
    Router.changePage("/login");
    return;
  }
  
  let headers = {
    "Content-Type": "application/json",
    Authorization: "Bearer " + Router.getJwt(),
  };
  
  let games = await fetch(GAME_SERVICE_HOST + "/?status=WAITING", {
    method: "GET",
    headers: headers,
  });
  
  let games_detail = (await games.json())["detail"];
  
  let pause_games = await fetch(GAME_SERVICE_HOST + "/?status=PAUSED", {
    method: "GET",
    headers: headers,
  });
  
  let pause_games_detail = (await pause_games.json())["detail"];
  
  if (pause_games.status === 200 && pause_games_detail.length > 0) {
    let game = pause_games_detail;
    if (game.length == 1) {
      let opponent = extractOpponentFromResponse(game[0]);
      await addAlertBox(
        "Game paused found with " + opponent,
        "success",
        document.getElementsByTagName("main")[0],
        2000,
      );
      Router.changePage("/pong/?opponent=" + opponent);
    } else if (game.length > 1) {
      await addAlertBox(
        document.getElementsByTagName("main")[0]
        );
        await new Promise((resolve) => setTimeout(resolve, 2000));
        alert.remove();
        Router.changePage("/pong/?opponent=" + opponent);
    }
    else if (game.length > 1) {
      await addAlertBox(
        "Error: more than one game found",
        "danger",
        document.getElementsByTagName("main")[0],
        3000,
      );
    }
  } else if (games.status === 200 && games_detail.length > 0) {
    let game = games_detail;
    if (game.length == 1) {
      let opponent = extractOpponentFromResponse(game[0]);
      await addAlertBox(
        "Game found with " + opponent,
        "success",
        document.getElementsByTagName("main")[0],
        2000,
      );
      Router.changePage("/pong/?opponent=" + opponent);
    } else if (game.length > 1) {
      await addAlertBox(
        "Error: more than one game found",
        "danger",
        document.getElementsByTagName("main")[0],
        3000,
      );
    }
  } else {
    let alert = await addAlertBox(
      "Joining queue...",
      "success",
      document.getElementsByTagName("main")[0],
    );
    response = await fetch(MATCHMAKING_SERVICE_HOST + "/queue/join/", {
      method: "POST",
      headers: headers,
    });
    if (response.status != 200) {
      alert.remove();
      await addAlertBox(
        "Error joining queue",
        "danger",
        document.getElementsByTagName("main")[0],
        3000,
      );
    }
  }
}          

async function enterLobby() {
  // Find any tournaments on waiting status or paused status
  
  // If JWT is not available, logout
  if (Router.getJwt() === null) {
    Router.changePage("/login");
    return;
  }
  
  // Get generic headers
  let headers = {
    "Content-Type": "application/json",
    Authorization: "Bearer " + Router.getJwt(),
  };
  
  // Look for a tournament that the user is currently playing
  // srcs/game/game_matchmaking/views.py:284 def get(self, request):
  let tournament = await fetch(GAME_SERVICE_HOST + "/tournament/", {
    method: "GET",
    headers: headers,
  });

  // If the players isnt in any tournament, let them join one
  let tournament_id
  if (tournament.status !== 200)
  {
    // srcs/game/game_matchmaking/views.py:257 def post(self, request):
    tournament = await fetch(GAME_SERVICE_HOST + "/tournament/", {
      method: "POST",
      headers: headers,
    });

    if (new_tournament.status === 200) {
      await addAlertBox(
        "Waiting for other players...",
        "success",
        document.getElementsByTagName("main")[0],
      );
    }
  } else {
    let tournament_id = tournament_detail[0].id;
    Router.changePage("/lobby/?tournament=" + tournament_id);
  }
}
                  