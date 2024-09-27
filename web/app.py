from flask import Flask, request
from flask_restful import Api, Resource
from pymongo import MongoClient
import bcrypt
import tensorflow
import keras
import requests
import numpy as np
from PIL import Image
from io import BytesIO

app = Flask(__name__)
api = Api(app)

client = MongoClient("mongodb://db:27017")
db = client.ImageClassificationDatabase
users = db["Users"]

inceptionV3 = keras.applications.InceptionV3
preprocess = keras.applications.inception_v3.preprocess_input
imagenet = keras.applications.imagenet_utils
img_array = tensorflow.keras.preprocessing.image.img_to_array

pre_trained_model = inceptionV3(weights="imagenet")

def userExist(username):
    user = users.find_one({"Username": username})
    if user:
        return True
    return False

def validPw(username, password):
    hashed_pw = users.find_one({"Username": username})["Password"]

    if bcrypt.hashpw(password.encode('utf8'), hashed_pw) == hashed_pw:
        return True
    return False

def countTokens(username):
    tokens = users.find_one({"Username": username})["Tokens"]
    return tokens

class Register(Resource):
    def post(self):
        postedData = request.get_json()

        username = postedData["username"]
        password = postedData["password"]

        if userExist(username):
            retJson = {
                'status_code': 301,
                'msg': 'Username já existente.'
            }
            return retJson
        
        hashed_pw = bcrypt.hashpw(password.encode('utf8'), bcrypt.gensalt())

        users.insert_one({
            "Username": username,
            "Password": hashed_pw,
            "Tokens": 10
        })

        retJson = {
            'status_code': 200,
            'msg': 'Cadastrado na API com sucesso.'
        }
        return retJson
    
class Classify(Resource):
    def post(self):
        postedData = request.get_json()

        username = postedData["username"]
        password = postedData["password"]
        url = postedData["url"]

        if not userExist(username):
            retJson = {
                'status_code': 301,
                'msg': 'Username inválido'
            }
            return retJson
        
        if not validPw(username, password):
            retJson = {
                'status_code': 302,
                'msg': 'Senha inválida'
            }
            return retJson
        
        num_tokens = countTokens(username)
        if num_tokens <= 0:
            retJson = {
                'status_code': 303,
                'msg': 'Sua quantidade de Tokens esgotou.'
            }
            return retJson
        
        if not url:
            retJson = {
                'status_code': 400,
                'msg': 'URL inválida.'
            }
            return retJson
        
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))

        img = img.resize((299, 299))
        img_arr = img_array(img)
        img_arr = np.expand_dims(img_arr, axis=0)
        img_arr = preprocess(img_arr)

        prediction = pre_trained_model.predict(img_arr)
        actual_prediction = imagenet.decode_predictions(prediction, top=5)

        retJson = {}
        for pred in actual_prediction[0]:
            retJson[pred[1]] = float(pred[2]*100)

        users.update_one({"Username": username}, {"$set": {"Tokens": num_tokens-1}})

        return retJson

    
api.add_resource(Register, '/register')
api.add_resource(Classify, '/classify')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
