from main import app

if __name__ == "__main__":
    app.config["JSON_SORT_KEYS"] = False
    app.run('127.0.0.1', port=5003, threaded=True)
