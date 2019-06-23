from flask import Blueprint, render_template, url_for, request, session, redirect, jsonify, abort
from flask_socketio import emit

from ..utils import decorators

# Import global variables
from ..config import GAMES, USER_DICT
from .. import socketio

mod = Blueprint('game', __name__, template_folder='templates')

## Game route
@mod.route('/<game_url>')
@decorators.login_required
def game(game_url):
    if GAMES.get(game_url):
        game = GAMES[game_url]
        player1 = game.player1
        player2 = game.player2
        if player1 == session.get('username'):
            board = game.chessboard.draw_chessboard()
            game_title = "{0} vs {1}".format(game.player1, game.player2)
            return render_template('game.html', game_title=game_title, board=board, player1=player1, player2=player2)
        else:
            board = game.chessboard.draw_chessboard_for_black()
            game_title = "{0} vs {1}".format(game.player1, game.player2)
            return render_template('game.html', game_title=game_title, board=board, player1=player2, player2=player1)
    abort(404)

@mod.route('/<game_url>/generateLegalMoves/<init_pos>')
@decorators.login_required
def generate_legal_moves(game_url, init_pos):
    if GAMES.get(game_url):
        return GAMES[game_url].generate_legal_moves(init_pos, session.get('username'))
    abort(404)

@mod.route('/<game_url>/makemove/<move>')
@decorators.login_required
def make_move(game_url, move):
    if GAMES.get(game_url):
        init_pos, final_pos = move.split('-')[0], move.split('-')[1]
        move = GAMES[game_url].make_move(init_pos, final_pos, session.get('username'))
        return jsonify(move)
    abort(404)

@mod.route('/<game_url>/getGameStatus')
@decorators.login_required
def fetch_game_status(game_url):
    if GAMES.get(game_url):
        status = GAMES[game_url].fetch_game_status()
        if len(status) == 1:
            return jsonify({
                'status': 'ongoing'
            })
        return jsonify({
            'status': 'finished',
            'result': status[2],
            'cause': status[1],
        })
    abort(404)

## Add a cryptographic id so that only server can dissolve games
## Something like /end/<server_id>/<game_url> or better yet 
## encrypt game urls.
@mod.route('/<game_url>/end')
@decorators.login_required
def end_game(game_url):
    if GAMES.get(game_url):
        player1 = GAMES[game_url].player1
        player2 = GAMES[game_url].player2
        USER_DICT['current_user_' + player1].in_game['status'] = False
        USER_DICT['current_user_' + player1].in_game['url'] = None
        USER_DICT['current_user_' + player2].in_game['status'] = False
        USER_DICT['current_user_' + player2].in_game['url'] = None
        GAMES.pop(game_url)
    return redirect(url_for('site.index'))

## Socket connections

@socketio.on('user_connect', namespace='/game')
def handle_connection(message):
    USER_DICT['current_user_' + session['username']].sessionid = request.sid
    emit('user_connect', "Hello!")

@socketio.on('make_move', namespace='/game')
def realtime_make_move(move_info):
    game_url = move_info['game_url']
    player1, player2 = game_url.split('-')[0], game_url.split('-')[1]
    reciever = player1 if player1!=session['username'] else player2
    if GAMES.get(game_url):
        move = GAMES[game_url].prev_move
    else:
        move = {'success': False}
    emit("make_move", move, room = USER_DICT['current_user_' + reciever].sessionid)