
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid, random, json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='eventlet')

games = {}

with open("word_list.json", "r", encoding="utf-8") as f:
    WORDS = json.load(f)["words"]

@app.route('/index')
def index():
    return render_template("index.html")

@app.route('/host')
def host():
    return render_template('host.html')

@app.route('/player')
def player():
    return render_template('player.html')

@app.route('/leaderboard')
def leaderboard():
    game_id = request.args.get('gameid')
    if not game_id:
        return "Game ID missing in URL.", 400
    return render_template('leaderboard.html', game_id=game_id)

@socketio.on('create_game')
def create_game(data):
    game_id = str(uuid.uuid4())[:5].lower()
    games[game_id] = {
        'host': request.sid,
        'players': {},
        'liar': None,
        'started': False,
        'word': None,
        'leaderboard': {}
    }
    join_room(game_id)
    emit('game_created', {'game_id': game_id}, room=request.sid)

@socketio.on('join_game')
def join_game(data):
    game_id = data['game_id']
    player_name = data['player_name']

    if game_id in games and not games[game_id]['started']:
        games[game_id]['players'][request.sid] = player_name
        games[game_id]['leaderboard'][player_name] = {'won': 0, 'lost': 0} 
        join_room(game_id)

        emit('player_joined', {'player_name': player_name}, room=request.sid)

        host_sid = games[game_id].get('host')
        if host_sid:
            emit('update_player_list', {'player_name': player_name}, room=host_sid)
    else:
        emit('join_error', {'message': 'Invalid or already started game ID'}, room=request.sid)
@socketio.on('submit_result')
def submit_result(data):
    game_id = data['game_id']
    player_name = data['player_name']
    result = data['result']

    game = games.get(game_id)
    if game and player_name in game['leaderboard']:
        if result == 'won':
            game['leaderboard'][player_name]['won'] += 1
        elif result == 'lost':
            pass

        leaderboard_scores = {}
        for player, record in game['leaderboard'].items():
            score = (record['won'] * 2)
            leaderboard_scores[player] = score

        emit('leaderboard_updated', {'leaderboard': leaderboard_scores}, room=game_id)




@socketio.on('start_game')
def start_game(data):
    game_id = data['game_id']
    game = games.get(game_id)
    if game and request.sid == game['host']:
        game['started'] = True
        game['liar'] = random.choice(list(game['players'].keys()))
        game['word'] = random.choice(WORDS)
        for sid in game['players']:
            if sid == game['liar']:
                emit('role_assigned', {'role': 'liar'}, room=sid)
            else:
                emit('role_assigned', {'role': 'word', 'word': game['word']}, room=sid)

@socketio.on('next_game')
def next_game(data):
    game_id = data['game_id']
    game = games.get(game_id)
    if game and request.sid == game['host']:
        game['liar'] = random.choice(list(game['players'].keys()))
        game['word'] = random.choice(WORDS)
        for sid in game['players']:
            if sid == game['liar']:
                emit('role_assigned', {'role': 'liar'}, room=sid)
            else:
                emit('role_assigned', {'role': 'word', 'word': game['word']}, room=sid)

@socketio.on('end_game')
def end_game(data):
    game_id = data['game_id']
    if game_id in games:
        for sid in games[game_id]['players'].keys():
            leave_room(game_id, sid=sid)
        del games[game_id]
        emit('game_ended', {'message': 'Game ended'}, room=request.sid)
        
@socketio.on('join_leaderboard')
def join_leaderboard(data):
    game_id = data['game_id']
    join_room(game_id)


@socketio.on('get_leaderboard')
def handle_get_leaderboard(data):
    game_id = data['game_id']
    if game_id in games:
        game = games[game_id]
        leaderboard_scores = {}
        for player, record in game['leaderboard'].items():
            score = (record['won'] * 2) - (record['lost'] * 1)
            leaderboard_scores[player] = score
        emit('leaderboard_updated', {'leaderboard': leaderboard_scores}, room=request.sid)



if __name__ == '__main__':
    socketio.run(app,host='0.0.0.0', port=5000, debug=True)
