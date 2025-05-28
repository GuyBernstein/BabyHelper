import uvicorn
import unittest
import os
import click
from app import create_app
from app.main import Base, engine
from app.main.model.baby import Baby

app = create_app()


# Create a click group to act as our manager
@click.group()
def manager():
    """FastAPI application manager."""
    pass


@manager.command()
def run():
    """Runs the FastAPI application"""
    uvicorn.run("manage:app", host="127.0.0.1", port=8000, reload=True)


@manager.command()
def test():
    """Runs the unit tests."""
    tests = unittest.TestLoader().discover('app/test', pattern='test*.py')
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if result.wasSuccessful():
        return 0
    return 1


@manager.group()
def db():
    """Database migration commands."""
    pass


@db.command()
def init():
    """Initializes migration repository."""
    os.system("alembic init migrations")
    # Update alembic.ini with correct database URI
    with open("alembic.ini", "r") as f:
        content = f.read()

    from app.main.config import Config
    content = content.replace("sqlalchemy.url = driver://user:pass@localhost/dbname",
                              f"sqlalchemy.url = {Config.SQLALCHEMY_DATABASE_URI}")

    with open("alembic.ini", "w") as f:
        f.write(content)

    # Update env.py to use our models
    with open("migrations/env.py", "r") as f:
        content = f.read()

    import_str = """from app.main import Base
from app.main.model.baby import Baby
from app.main.model.growth import Growth
from app.main.model.feeding import Feeding
from app.main.model.sleep import Sleep
from app.main.model.diaper import Diaper
from app.main.model.health import Health
from app.main.model.user import User
from app.main.model.parent_child_schema import CoParentInvitation, Notification
from app.main.model.doctor_visit import DoctorVisit
from app.main.model.medication import Medication
from app.main.model.pumping import Pumping

target_metadata = Base.metadata"""
    content = content.replace("target_metadata = None", import_str)

    with open("migrations/env.py", "w") as f:
        f.write(content)

    print("Alembic initialized successfully with your database configuration.")


@db.command()
@click.option('--message', default='database migration', help='Migration message')
def migrate(message):
    """Generates a new migration"""
    os.system(f"alembic revision --autogenerate -m '{message}'")
    print(f"Migration created with message: {message}")


@db.command()
def upgrade():
    """Applies all available migrations."""
    os.system("alembic upgrade head")
    print("Database upgraded successfully.")


@db.command()
def downgrade():
    """Reverts last migration."""
    os.system("alembic downgrade -1")
    print("Downgraded one migration.")

@db.command()
def current():
    """Shows current database revision."""
    os.system("alembic current")

@db.command()
def heads():
    """Shows available migration heads."""
    os.system("alembic heads")

@db.command()
def history():
    """Shows migration history."""
    os.system("alembic history")

@db.command()
@click.argument('revision')
def stamp(revision):
    """Stamps database with specific revision without running migrations."""
    os.system(f"alembic stamp {revision}")

@db.command()
def show():
    """Shows available revisions."""
    os.system("alembic show head")

if __name__ == '__main__':
    manager()