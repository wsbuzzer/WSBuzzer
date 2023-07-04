import asyncio
from websockets.server import serve
from websockets.exceptions import ConnectionClosed
import json
import random
import sys

class Game:
    def __init__(self, game_master, game_name, game_password):
        self.master = game_master #The game master WebScoket
        self.name = game_name
        self.password = game_password
        self.players = {}
        self.buzz_enabled = False

    async def buzz(self,player_socket):
        '''
        Inform the game master that someone buzzed and prevent the others from buzzing
        '''
        if not(self.buzz_enabled):
            to_send = {"type":"info","message":"You can't buzz now"}
            data = json.dumps(to_send)
            await player_socket.send(data)
        else:
            self.buzz_enabled=False
            to_send = {"type":"buzzed","player_name":self.players[player_socket]}
            data = json.dumps(to_send)
            for p in self.players.keys():
                await p.send(data)
            await self.master.send(data)


    async def enable_buzz(self):
        '''
        Re-enable the buzzer for all the players
        '''
        to_send = {"type":"enable_buzz", "message":"You can now buzz again"}
        data = json.dumps(to_send)
        for p in self.players.keys():
            await p.send(data)
        self.buzz_enabled=True

   
   

class Server:
    def __init__(self,addr="0.0.0.0", port=8765):
        self.games = []
        self.addr = addr
        self.port = port
    
    async def handle(self,websocket):
        try:
            async for message in websocket:
                print(f"Message received : {message}")
                to_send=None
                data = json.loads(message)

                match data["action"]:

                    case "check_join":
                        can_join, cause = self.can_join_game(data["game_name"],data["password"])
                        if can_join:
                            to_send = {"type":"join", "message":""}
                        else:
                            if cause==1:
                                to_send = {"type":"error", "message":"There is no game with this name"}
                            elif cause==2:
                                to_send = {"type":"error", "message":"You didn't provide the right password"}

                    case "check_create":
                        if self.can_create_game(data["game_name"]):
                            to_send = {"type":"create", "message":""}
                        else:
                            to_send={"type":"error", "message":"There is already a game with this name"}
                    
                    
                    case "create":
                        if self.can_create_game(data["game_name"]):
                            self.games.append(Game(websocket, data["game_name"], data["password"]))
                            to_send = {"type":"info", "message":"The game has been created"}
                        else:
                            to_send = {"type":"error", "message":"There is already a game with this name"}

                    case "join":
                        can_join, game = self.can_join_game(data["game_name"],data["password"])
                        if can_join:
                            game.players[websocket] = data["player_name"]
                            to_send = {"type":"info", "message":"You are successfully connected to the game"}
                        else:
                            if game==1:
                                to_send = {"type":"error", "message":"There is no game with this name"}
                            elif game==2:
                                to_send = {"type":"error", "message":"You didn't provide the right password"}

                    case "buzz":
                        to_send = {"type":"error", "message":"You're linked with no game"}
                        for g in self.games:
                            if websocket in g.players.keys():
                                to_send = {"type":"info", "message":"You buzzed"}
                                await g.buzz(websocket)
                                break

                    case "reset_buzz":
                        to_send = {"type":"error", "message":"You're linked with no game"}
                        for g in self.games:
                            if websocket == g.master:
                                to_send = {"type":"info", "message":"You reseted the buzzer"}
                                await g.enable_buzz()
                                break

                    case "disconnect":
                        for g in self.games:
                            if websocket in g.players.keys():
                                g.players.pop(websocket)
                                break
                
                        if websocket == g.master:
                            self.games.remove(g)
                            del g
                            break

                    case _:
                        to_send = {"type":"error", "message":"This isn't an allowed action"}

                await websocket.send(json.dumps(to_send))

        except ConnectionClosed: #The connexion with client has been closed/lost
            for g in self.games:
                if websocket in g.players.keys():
                    g.players.pop(websocket)
                    break
                
                if websocket == g.master:
                    del g
                    self.games.remove(g)
                    break

            

    async def main(self):
        print(f"Starting server on {self.addr}:{self.port}" )
        async with serve(self.handle, self.addr, self.port):
            await asyncio.Future()  # run forever

    def can_create_game(self,game_name):
        '''
        Check if there is already the game with the given name
        '''
        for g in self.games:
            if g.name==game_name:
                return False
        return True

    def can_join_game(self,game_name,game_password):
        '''
        Check if there is a game with the given name and, if so, check if the right password was provided
        '''
        for g in self.games:
            if g.name == game_name:
                if g.password == game_password:
                    return True, g
                return False, 2 #A game with the given name exists but bad password
        return False, 1 #No game exists with this name


    
    def run(self):
        asyncio.run(self.main())


if __name__ == "__main__":
    if len(sys.argv) == 2:
        serv = Server(sys.argv[1])
    elif len(sys.argv) == 3:
        serv = Server(sys.argv[1], int(sys.argv[2]))
    else:
        serv = Server()
    serv.run()
