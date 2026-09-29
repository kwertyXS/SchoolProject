from flask import Flask


def create_app():
    app = Flask(__name__)

    from . import api, views
    app.register_blueprint(api.bp)
    app.register_blueprint(views.bp)

    return app


def main() -> None:
    create_app().run()
