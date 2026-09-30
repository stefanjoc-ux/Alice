"""Safety of the test harness itself: dummy keys win over a real .env, and the real data folder is untouched."""
import _util
from _util import t
import os
import app, desktop
t('OpenAI key is the dummy, even with a real .env present', os.getenv('OPENAI_API_KEY') == 'test-key-not-real')
t('Anthropic and xAI keys are dummies too', os.getenv('ANTHROPIC_API_KEY') == os.getenv('XAI_API_KEY') == 'test-key-not-real')
t('model libraries point at a dead local address', os.getenv('OPENAI_BASE_URL', '').startswith('http://127.0.0.1:9'))
t('data folder is a throwaway test folder', os.path.basename(os.environ['AISUBSTRATE_DATA_DIR']).startswith('alice-test-'))
t('the app is using the throwaway folder', str(app.DB_PATH if hasattr(app, 'DB_PATH') else __import__('substrate_store').DB).startswith(os.environ['AISUBSTRATE_DATA_DIR']))
