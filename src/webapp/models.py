"""
    Classes for describing tables in the database and additional functions for
    manipulating them.
"""

import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug import exceptions as excp

db = SQLAlchemy()


class Games(db.Model):
    """
       This is the Games model in the database. It is important that the
       inserted values match the column values. Token column value cannot
       be String when a long hex is given.
    """

    gid = db.Column(db.NVARCHAR(32), primary_key=True)
    session_num = db.Column(db.Integer, default=1)
    labels = db.Column(db.String(64))
    date = db.Column(db.DateTime)


class Scores(db.Model):
    """
        This is the Scores model in the database. It is important that the
        inserted values match the column values.
    """

    sid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(32))
    score = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date)


class PlayerInGame(db.Model):
    """
        Table for attributes connected to a player in the game. gid is a
        foreign key to the game table.
    """
    token = db.Column(db.NVARCHAR(32), primary_key=True)
    gid = db.Column(db.NVARCHAR(32), nullable=False)
    play_time = db.Column(db.Float, nullable=False)


# Functions to manipulate the tables above
def create_tables(app):
    """
        The tables will be created if they do not already exist.
    """
    with app.app_context():
        db.drop_all()  # Temporary
        db.create_all()

    return True


def insert_into_games(gid, labels, date):
    """
        Insert values into Games table.

        Parameters:
        gid : random uuid.uuid4().hex
        labels: list of labels
        date: datetime.datetime
    """
    if (isinstance(gid, str)
            and isinstance(labels, str)
            and isinstance(date, datetime.datetime)):
        try:
            game = Games(gid=gid, labels=labels, date=date)
            db.session.add(game)
            db.session.commit()
            return True
        except Exception as e:
            raise Exception("Could not insert into games :" + str(e))
    else:
        raise excp.BadRequest("Gid has to be string, labels has to be string "
                              "and date has to be datetime.datetime.")


def insert_into_scores(name, score, date):
    """
        Insert values into Scores table.

        Parameters:
        name: user name, string
        score: float
        date: datetime.date
    """
    score_int_or_float = isinstance(score, float) or isinstance(score, int)

    if (isinstance(name, str)
            and score_int_or_float
            and isinstance(date, datetime.date)):
        try:
            score = Scores(name=name, score=score, date=date)
            db.session.add(score)
            db.session.commit()
            return True
        except Exception as e:
            raise Exception("Could not insert into scores: " + str(e))
    else:
        raise excp.BadRequest("Name has to be string, score can be int or "
                              "float and date has to be datetime.date.")


def insert_into_player_in_game(token, gid, play_time):
    """
        Insert values into PlayerInGame table.

        Parameters:
        token: random uuid.uuid4().hex
        gid: random uuid.uuid4().hex
        play_time: float
    """
    if (isinstance(token, str)
            and isinstance(gid, str)
            and isinstance(play_time, float)):
        try:
            player_in_game = PlayerInGame(token=token, gid=gid,
                                          play_time=play_time)
            db.session.add(player_in_game)
            db.session.commit()
            return True
        except Exception as e:
            raise Exception("Could not insert into games: " + str(e))
    else:
        raise excp.BadRequest("Token has to be string, gid has to be string "
                              "and play time has to be float.")


def get_record_from_game(gid):
    """
        Return the game record with the corresponding gid.
    """
    game = Games.query.get(gid)
    if game is None:
        raise excp.BadRequest("Gid invalid or expired")

    return game


def get_record_from_player_in_game(token):
    """
        Return the player in game record with the corresponding token.
    """
    player_in_game = PlayerInGame.query.get(token)
    if player_in_game is None:
        raise excp.BadRequest("Token invalid or expired")

    return player_in_game


# DELETABLE
def update_game(gid, session_num, play_time):
    """
        Update game record for the incomming token with the given parameters.
    """
    try:
        game = Games.query.get(gid)
        game.session_num += 1
        game.play_time = play_time
        db.session.commit()
        return True
    except Exception:
        raise Exception("Couldn't update game.")


# ALTERNATIVE FUNC FOR UPDATE GAME TO ALSO WORK FOR MULTI
def update_game_for_player(gid, token, session_num, play_time):
    """
        Docstring.
    """
    try:
        game = Games.query.get(gid)
        game.session_num += 1
        player_in_game = PlayerInGame.query.get(token)
        player_in_game.play_time = play_time
        db.session.commit()
        return True
    except Exception as e:
        raise Exception("Could not update: " + str(e))


def delete_session_from_game(gid):
    """
        To avoid unecessary data in the database this function is called by
        the api after a session is finished. The record in games table,
        connected to the particular gid, is deleted.
    """
    try:
        game = Games.query.get(gid)
        db.session.query(PlayerInGame).filter(
            PlayerInGame.gid == gid).delete()
        db.session.delete(game)
        db.session.commit()
        return "Record deleted."
    except AttributeError as e:
        db.session.rollback()
        raise AttributeError("Couldn't find gid: " + str(e))


def delete_old_games():
    """
        Delete records in games older than one hour.
    """
    try:
        games = db.session.query(Games).filter(Games.date < (
            datetime.datetime.today() - datetime.timedelta(hours=1))).all()
        for game in games:
            db.session.query(PlayerInGame).filter(
                PlayerInGame.gid == game.gid).delete()
            db.session.delete(game)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        raise Exception("Couldn't clean up old game records: " + str(e))


def get_daily_high_score():
    """
        Function for reading all daily scores.

        Returns list of dictionaries.
    """
    try:
        today = datetime.date.today()
        #filter by today and sort by score
        top_n_list = Scores.query.filter_by(
            date=today).order_by(Scores.score.desc()).all()
        #structure data
        new = [{"name": player.name, "score": player.score}
               for player in top_n_list]
        return new

    except AttributeError:
        print("Could not read daily highscore from database")
        return AttributeError("Could not read daily highscore from database")


def get_top_n_high_score_list(top_n):
    """
        Funtion for reading tootal top n list from database.

        Parameter: top_n, number of players in top list.

        Returns list of dictionaries.
    """
    try:
        #read top n high scores
        top_n_list = Scores.query.order_by(
            Scores.score.desc()).limit(top_n).all()
        #strucutre data
        new = [{"name": player.name, "score": player.score}
               for player in top_n_list]
        return new

    except AttributeError:
        print("Could not read top " + str(top_n) + " high score from database")
        return AttributeError("Table does not exist.")


def drop_table(table):
    """
        Function for dropping a table, or all.
    """
    # Calling 'drop_table' with None as parameter means dropping all tables.
    db.drop_all(bind=table)
