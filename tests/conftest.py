import os
import tempfile

os.environ["BUBO_DATA"] = tempfile.mkdtemp(prefix="bubo-test-")
os.environ["BUBO_PASSWORD"] = "secret"
