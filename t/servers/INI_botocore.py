from Pyjo.INI import load
from Pyjo.Test import *

import importlib.util
import os
import tempfile


# Not in Mojolicious: the files of AWS of Pyjo.INI next to what botocore reads of them, with configparser, in the
# dependency group "servers"

if not importlib.util.find_spec('botocore'):
    plan(skip_all='needs the dependency group "servers", without botocore')

import botocore.configloader  # noqa: E402


FILES = {
    'config': """# The default profile
[default]
region = eu-central-1
output = json

[profile dev]
sso_session = my-sso
sso_account_id = 111122223333
sso_role_name = Developer
region: us-west-2
s3 =
    max_concurrent_requests = 20
    addressing_style = path
cli_pager =

; Single sign-on
[sso-session my-sso]
sso_start_url = https://my-sso-portal.awsapps.com/start
sso_region = us-east-1
sso_registration_scopes = sso:account:access

[services dev-s3]
s3 =
  endpoint_url = http://localhost:4566
""",
    'credentials': """[default]
aws_access_key_id = AKIAIOSFODNN7EXAMPLE
aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

[dev]
aws_access_key_id=AKIAI44QH8DHBEXAMPLE
aws_secret_access_key=je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY
aws_session_token = IQoJb3JpZ2luX2VjEXAMPLE
""",
}

with tempfile.TemporaryDirectory() as dir:
    for name, content in FILES.items():
        with subtest(f'~/.aws/{name}'):
            path = os.path.join(dir, name)
            with open(path, 'w') as file:
                file.write(content)
            is_deeply_ok(load(content), botocore.configloader.raw_config_parse(path), 'same as raw_config_parse')

done_testing()
