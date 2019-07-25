import time
import random

from flask import Blueprint, render_template, url_for, request, session, redirect, jsonify
from datetime import timedelta, datetime

import bcrypt as hash_pass
import re as regex

mod = Blueprint('site', __name__, template_folder='templates')

# Relative imports
from .users import addNewUserToDatabase, loadUser
from ..utils import exceptions
from ..utils import decorators
from ..utils import game

# Import global variables and settings
from ..config import PLAYERS_QUEUE, USER_DICT, FEN_NOTATION_REGEX ,USERNAME_REGEX, EMAIL_PATTERN_COMPILED, GAMES, TERMINAL_COLORS

# Database initialisation
from .. import database
db = database.db
users = db.users # object pointing to users database!

# Make users to be logged in for 5 days!
@mod.before_app_first_request
def make_session_permanent():
    session.permanent = True
    mod.permanent_session_lifetime = timedelta(days=5)
    
@mod.before_app_first_request
def load_user_from_session():
    if session.get('username'):
        USER_DICT['current_user_'+str(session['username'])] = loadUser(users, session['username'])[0]

@mod.before_request
def init():
    print(
        TERMINAL_COLORS['CYELLOW'] + 
        TERMINAL_COLORS['CBOLD'], end=""
    )
    print("Current Users : ", end="")
    print(USER_DICT)
    print("Current Games : ", end="")
    print(GAMES)
    print(
        TERMINAL_COLORS['CEND'] + 
        TERMINAL_COLORS['CEND'], end=""
    )

### View functions start ###

@mod.route('/login', methods=['GET', 'POST'])
@decorators.logout_required
def login():
    if request.method=='POST':
        user = loadUser(users, request.form['username'])
        if user[0] and user[1]==1:
            if hash_pass.hashpw(request.form['password'].encode('utf-8'), user[0].password)==user[0].password:
                session['username'] = request.form['username']
                USER_DICT['current_user_' + str(session['username'])] = user[0]
                return redirect(url_for('site.index'))
            else:
                return render_template('login.html', error_code=-3, script=None)
        elif user[1]==0:
            return redirect(url_for('site.verify', username=user[0].username))
        return render_template('login.html', error_code=-1, script=None)
    return render_template('login.html', error_code=0, script=None)

from . import mailing

@mod.route('/register', methods=['POST'])
@decorators.logout_required
def register():
    # Script adds a little js code to login.html so as in to keep registration form
    # in view after template is rendered again due to invalid register attempt!
    script = """
    <script>
        $(document).ready(function(){
            $("#register-form").show();
            $("#login-form").hide();
        })
    </script>
    """

    valid_email = bool(regex.match(EMAIL_PATTERN_COMPILED, request.form['email']))
    valid_username = bool(regex.match(USERNAME_REGEX, request.form['username']))

    if valid_email and valid_username:
        existing_user = users.find_one({
            'username' : request.form['username']
        })
        existing_email = users.find_one({
            'email' : request.form['email']
        })
        if existing_email is None and existing_user is None:
            if request.form['password']==request.form['confirm_password']:
                # Code to randomly assign an image for the user! 
                # Later add an interface for the users to be able to select their own profile pictures!
                random_image = "/static/Images/profile_pics/" + str(random.randint(1, 17)) + ".png"
                hash_password = hash_pass.hashpw(request.form['password'].encode('utf-8'), hash_pass.gensalt())
                # This method adds an user to database and sends a verification mail!
                addNewUserToDatabase(
                    request.form['username'], 
                    hash_password, 
                    request.form['email'], 
                    random_image, 
                    request.form['first_name'], 
                    request.form['last_name'], 
                    users,
                )
                current_user = loadUser(users, request.form['username'])[0]
                #Send email verification
                response = mailing.sendMail(current_user._id, current_user.email, current_user.username)
                if not response:
                    return redirect(url_for('site.verify', error_code=6, script=script))
                return redirect(url_for('site.verify', username=current_user.username))
            return render_template('login.html', error_code=5, script=script)
        elif existing_email:
            return render_template('login.html', error_code=4, script=script)
        return render_template('login.html', error_code=3, script=script)
    elif valid_email is None:
        return render_template('login.html', error_code=2, script=script)
    return render_template('login.html', error_code=1, script=script)

# Link user for verification!
@mod.route('/verify/<username>', methods=['GET', 'POST'])
@decorators.logout_required
def verify(username):
    current_user = loadUser(users, username)[0]
    if request.method=='POST':
        if request.form['activation_link'].strip(' ')==current_user._id:
            session['username'] = current_user.username
            current_user.updateUserVerificationStatus()
            USER_DICT['current_user_' + str(session['username'])] = current_user
            return redirect(url_for('site.index'))
        return render_template('verify.html', username=username ,error_code=1)
    return render_template('verify.html', username=username, error_code=0)

# Route to resend verification mail to user
@mod.route('/verify/<username>/retry', methods=["POST"])
@decorators.logout_required
def retry(username):
    current_user = loadUser(users, username)[0]
    response = mailing.sendMail(current_user._id, current_user.email, current_user.username)
    return jsonify({'response': response})

## Index Page

@mod.route('/')
@decorators.login_required
def index():
    new_chess_board = USER_DICT['current_user_' + str(session['username'])].chessboard.draw_chessboard()
    current_user = USER_DICT['current_user_' + str(session['username'])]
    today = { # This variable contains special things related to today
        "first": "Games Won = 0",
        "second": "Winning Streak = 0",
        "third": "Best Win = 1200",
    }
    return render_template('index.html', user=current_user, board=new_chess_board, today=today)

@mod.route('/board/flip/<configuration>')
@decorators.login_required
def flipBoard(configuration):
    print(configuration)
    flipped_board = USER_DICT['current_user_' + str(session['username'])].chessboard.draw_chessboard(configuration)
    return jsonify({"board": flipped_board})

@mod.route('/board/reset')
@decorators.login_required
def resetBoard():
    fen_notation = request.args.get('fen', None)
    if fen_notation == 'default':
        USER_DICT['current_user_' + str(session['username'])].chessboard.reset_chessboard()
    else:
        valid_fen = bool(regex.match(FEN_NOTATION_REGEX, fen_notation))
        if not valid_fen:
            USER_DICT['current_user_' + str(session['username'])].chessboard.reset_chessboard()
        else:
            try:
                USER_DICT['current_user_' + str(session['username'])].chessboard.reset_chessboard(fen_notation)
            except exceptions.InvalidFenNotation:
                USER_DICT['current_user_' + str(session['username'])].chessboard.reset_chessboard()
    reset_board = USER_DICT['current_user_' + str(session['username'])].chessboard.draw_chessboard()
    return jsonify({"board": reset_board})

@mod.route('/board/generateLegalMoves/<init_pos>')
@decorators.login_required
def generateLegalMoves(init_pos):
    try:
        moves = USER_DICT['current_user_' + str(session['username'])].chessboard.generate_legal_moves(init_pos)
    except exceptions.SideNotAuthorizedToMakeMove as error:
        return jsonify({'moves': []})
    return jsonify({'moves': moves})

@mod.route('/board/generateFenNotation')
@decorators.login_required
def generateFenNotation():
    notation = USER_DICT['current_user_' + str(session['username'])].chessboard.fen_notation
    return jsonify({'notation': notation})

@mod.route('/board/makemove/<move>')
@decorators.login_required
def make_move(move):
    positions = move.split('-')
    dest_square = positions[2] if len(positions)==3 else None
    try:
        changes = USER_DICT['current_user_' + str(session['username'])].chessboard.make_move(positions[0], positions[1], dest_square)
    except exceptions.InvalidMoveError as error:
        print(error)
        return jsonify({'success': False})
    except exceptions.SideNotAuthorizedToMakeMove as error:
        print(error)
        return jsonify({
            'success': False,
            'auth': False,
            })
    except exceptions.Draw as result:
        return jsonify({
            'gameFinished': True,
            'result': 0.5,
            'cause': result.cause,
        })
    except exceptions.Checkmate as result:
        return jsonify({
            'gameFinished': True,
            'result': result.result,
        })
    return jsonify({
        'success': True,
        'changes': changes,
    })

@mod.route('/board/getGameStatus')
@decorators.login_required
def get_game_status():
    status = USER_DICT['current_user_' + str(session['username'])].chessboard.fetch_game_status()
    if len(status) == 1:
        return jsonify({
            'status': 'ongoing'
        })
    return jsonify({
        'status': 'finished',
        'result': status[2],
        'cause': status[1],
    })

# Handle game loading here
@mod.route('/find_game')
@decorators.login_required
def find_game():
    if not USER_DICT['current_user_' + str(session['username'])].in_game['status']:
        game.make_game(session, PLAYERS_QUEUE, GAMES)
        end_time = (datetime.now() + timedelta(seconds=10)).time()
        while end_time >= datetime.now().time():
            new_game = game.get_game(session, GAMES)
            if new_game:
                USER_DICT['current_user_' + str(session['username'])].in_game['status'] = True
                USER_DICT['current_user_' + str(session['username'])].in_game['url'] = new_game
                return jsonify({"url": new_game})
            time.sleep(1)
        PLAYERS_QUEUE.remove(session['username'])
        return jsonify({"url": None})
    url = USER_DICT['current_user_' + str(session['username'])].in_game['url']
    return jsonify({"url": url})

# logout routine
@mod.route('/logout')
@decorators.login_required
def logout():
    USER_DICT.pop('current_user_' + str(session['username']))
    session.pop('username')
    return redirect(url_for('site.login'))