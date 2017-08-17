import sys
from flask import Flask
from flask_restful import Resource, Api

app = Flask(__name__)
api = Api(app)

tk_path = ''


class TokenServiceReader(Resource):

    def __init__(self):
        self.previous_token = ''

    def get(self, token):
        if token != self.previous_token:
            self.previous_token = token

            with open(tk_path, "w") as tk_file:
                print("[*] Token update:", token)
                tk_file.write(token)


api.add_resource(TokenServiceReader, '/token/<string:token>')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: {} token_creation_path".format(sys.argv[0]))
        sys.exit(1)

    tk_path = sys.argv[1]

    app.run(host='0.0.0.0')
