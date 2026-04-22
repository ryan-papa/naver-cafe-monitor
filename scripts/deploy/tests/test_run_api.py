from scripts.deploy.run_api import parse_dotenv


SINGLE_LINE_ENV = (
    "NAVER_ID=hosekim92\n"
    "LOG_LEVEL=INFO\n"
    "AUTH_RSA_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\\nMIIEv...Q==\\n-----END PRIVATE KEY-----\\n\n"
    "AUTH_RSA_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\\nMIIBI...AB\\n-----END PUBLIC KEY-----\\n\n"
    "AUTH_AES_KEY=base64payload==\n"
    "AUTH_JWT_SECRET=another64==\n"
)

MULTI_LINE_ENV = (
    "AUTH_RSA_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n"
    "MIIEvAIBADANBgkq\n"
    "-----END PRIVATE KEY-----\n"
    "AUTH_AES_KEY=base64payload==\n"
)


def test_parse_dotenv_single_line_pem_does_not_swallow_following_keys():
    env = parse_dotenv(SINGLE_LINE_ENV)
    assert env["NAVER_ID"] == "hosekim92"
    assert env["AUTH_RSA_PRIVATE_KEY"].startswith("-----BEGIN PRIVATE KEY-----")
    assert env["AUTH_RSA_PRIVATE_KEY"].endswith("-----END PRIVATE KEY-----\\n")
    assert env["AUTH_RSA_PUBLIC_KEY"].startswith("-----BEGIN PUBLIC KEY-----")
    assert env["AUTH_AES_KEY"] == "base64payload=="
    assert env["AUTH_JWT_SECRET"] == "another64=="


def test_parse_dotenv_multi_line_pem_still_works():
    env = parse_dotenv(MULTI_LINE_ENV)
    assert "-----BEGIN PRIVATE KEY-----" in env["AUTH_RSA_PRIVATE_KEY"]
    assert "-----END PRIVATE KEY-----" in env["AUTH_RSA_PRIVATE_KEY"]
    assert env["AUTH_AES_KEY"] == "base64payload=="
