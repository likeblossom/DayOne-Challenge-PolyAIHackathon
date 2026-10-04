"""Build with a persistent local signing key; never commit .signing/."""
import os,secrets,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'.signing';folder.mkdir(mode=0o700,exist_ok=True)
props=folder/'signing.properties';key=folder/'sanad-release.jks'
if not props.exists():
    if key.exists():raise SystemExit('Signing key exists without properties; recover its password instead of replacing it.')
    password=secrets.token_urlsafe(36)
    env=dict(os.environ,SANAD_SIGNING_PASSWORD=password)
    subprocess.run(['keytool','-genkeypair','-keystore',str(key),'-storetype','JKS','-alias','sanad','-keyalg','RSA','-keysize','3072','-validity','10000','-dname','CN=Sanad Hackathon','-storepass:env','SANAD_SIGNING_PASSWORD','-keypass:env','SANAD_SIGNING_PASSWORD'],env=env,check=True)
    props.write_text(f'storePassword={password}\nkeyPassword={password}\n');props.chmod(0o600);key.chmod(0o600)
subprocess.run(['./gradlew','--no-daemon','--max-workers=2',':app:assembleRelease',':app:testDebugUnitTest',':app:lintRelease'],cwd=ROOT,check=True)
