import uvicorn
import unittest
from app import create_app

app = create_app()

def run():
    """Runs the FastAPI application"""
    uvicorn.run("__main__:app", host="127.0.0.1", port=8000, reload=True)

def test():
    """Runs the unit tests."""
    tests = unittest.TestLoader().discover('app/test', pattern='test*.py')
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    if result.wasSuccessful():
        return 0
    return 1

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == 'run':
            run()
        elif sys.argv[1] == 'test':
            test()
    else:
        run()
