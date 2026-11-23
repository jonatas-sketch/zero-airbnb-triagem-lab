from hypothesis import settings
from schemathesis import checks, openapi
from triage_api import app

schema = openapi.from_asgi("/openapi.json", app)
cases = 0
errors = 0

@schema.parametrize()
@settings(max_examples=24, deadline=None)
def test_triage_schema(case):
    global cases, errors
    response = case.call()
    cases += 1
    errors += int(response.status_code >= 500)
    case.validate_response(response, checks=[checks.not_a_server_error, checks.response_schema_conformance])

def teardown_module():
    print(f"Schemathesis OpenAPI conformance: {cases} generated cases, {errors} server errors")
