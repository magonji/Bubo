import os
import tempfile

os.environ["BUBO_DATA"] = tempfile.mkdtemp(prefix="bubo-test-")
os.environ["BUBO_PASSWORD"] = "secret"
os.environ["BUBO_RADAR_HOURS"] = "0"   # no background radar in tests
os.environ["BUBO_ORCID_LOOKUP"] = "0"  # nor looking up authors' iDs
