"""Start the local PlateScope web application."""

import mysql.connector

from api.app import app
from utils.database_manager import initialize_database


if __name__ == "__main__":
    try:
        initialize_database()
    except mysql.connector.Error as error:
        raise SystemExit(
            "Could not connect to MySQL or initialize its tables. "
            "Check that MySQL is running, the numberplate database exists, "
            "and the .env credentials are correct."
        ) from error
    app.run(host="127.0.0.1", port=5000, debug=False)
