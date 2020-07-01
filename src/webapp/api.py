#! /usr/bin/env python
import uuid
import random
import time
import sys
import os
from webapp import storage
from webapp import models
from customvision.classifier import Classifier
from io import BytesIO
from PIL import Image
from flask import Flask
from flask import request
from flask import jsonify
from flask_sqlalchemy import SQLAlchemy

print("ok")
base_url = Keys.get("BASE_IMAGE_URL")
print(base_url)
# Global variables
app = Flask(__name__)
app.config.from_object("webapp.config.Config")
models.db.init_app(app)
classifier = Classifier()


@app.route("/")
def hello():
    return "Yes, we're up"


@app.route("/startGame")
def start_game():
    """
        Starts a new game. A unique token is generated to keep track of game.
        A random label is chosen for the player to draw. Startime is
        recorded to calculate elapsed time when the game ends. Name can be
        either None or a name and is not unique. Will be sent from frontend.
    """
    # start a game and insert it into the games table
    start_time = time.time()
    token = uuid.uuid4().hex
    label = random.choice(labels)
    name = None  # TODO: name not needed until highscore row is created
    models.insert_into_games(token, name, start_time, label)

    # return game data as json object
    data = {
        "token": token,
        "label": label,
        "start_time": start_time,
    }
    return jsonify(data), 200


@app.route("/submit_answer", methods=["POST"])
def submit_answer():
    """
        Endpoint for user to submit drawing. Drawing is classified with Custom
        Vision.The player wins if the classification is correct and the time
        used is less than the time limit.
    """
    stop_time = time.time()

    # Check if image submitted correctly
    if "file" not in request.files:
        return "No image submitted", 400
    image = request.files["image"]
    if not allowed_file(image):
        return "Image does not satisfy constraints", 415

    # get classification from customvision
    best_guess, certainty = classifier.predict_png(image)

    # use token submitted by player to find game
    token = request.values["token"]
    name, start_time, label = models.query_game(token)

    # check if player won the game
    time_used = stop_time - start_time
    has_won = time_used < time_limit and best_guess == label

    # save image in blob storage
    storage.save_image(image, label)

    # save score in highscore table
    name = request.values["name"]
    score = time_used
    models.insert_into_scores(name, score)

    # return json response
    data = {
        "certainty": classification,
        "guess": best_guess,
        "correctLabel": label,
        "hasWon": has_won,
        "timeUsed": time_used,
    }
    return jsonify(data), 200


def allowed_file(image):
    """
        Check if image satisfies the constraints of Custom Vision.
    """
    if image.filename == "":
        return False

    # Check if the filename is of PNG type
    png = image.filename.endswith(".png") or image.filename.endswith(".PNG")
    # Ensure the file isn't too large
    too_large = len(image.read()) > 4000000
    # Ensure the file has correct resolution
    image.seek(0)
    height, width = Image.open(BytesIO(image.stream.read())).size
    image.seek(0)
    correct_res = (height >= 256) and (width >= 256)
    if not png or too_large or not correct_res:
        return False
    else:
        return True


if __name__ == "__main__":
    # creates table if does not exist
    models.create_tables(app)

    app.run(debug=True)
