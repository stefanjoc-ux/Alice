"""ElevenLabs voice: Scribe speech-to-text and text-to-speech. The API key never leaves the server."""
import base64
import binascii
import os
import re
import httpx
import usage_meter

API = 'https://api.elevenlabs.io/v1'
STT_MODEL = os.getenv('ELEVENLABS_STT_MODEL', 'scribe_v2')
TTS_MODEL = os.getenv('ELEVENLABS_TTS_MODEL', 'eleven_multilingual_v2')
MAX_AUDIO = 20 * 1024 * 1024
MAX_SPEAK = 4500          # characters per reply read aloud; keeps credit use bounded
AUDIO_TYPES = {'audio/webm': 'webm', 'audio/ogg': 'ogg', 'audio/mp4': 'm4a', 'audio/mpeg': 'mp3', 'audio/wav': 'wav'}
_voices = None


def configured():
    return bool(os.getenv('ELEVENLABS_API_KEY'))


def _key():
    key = os.getenv('ELEVENLABS_API_KEY')
    if not key: raise ValueError('Set ELEVENLABS_API_KEY in .env and restart.')
    return key


def _detail(response):
    """ElevenLabs' own explanation, shortened. Never includes the API key."""
    try:
        detail = response.json().get('detail', '')
        if isinstance(detail, dict): detail = detail.get('message') or detail.get('status') or ''
        if isinstance(detail, list): detail = '; '.join(str(d.get('msg', d)) if isinstance(d, dict) else str(d) for d in detail)
        return str(detail)[:300]
    except Exception:
        return response.text[:300]


def _check(response):
    if response.status_code < 400: return
    detail = _detail(response)
    suffix = f': {detail}' if detail else '.'
    if response.status_code == 401: raise ValueError('ElevenLabs rejected the API key or its permissions' + suffix)
    if response.status_code in (402, 429): raise ValueError('ElevenLabs credits or rate limit reached' + suffix)
    raise ValueError(f'ElevenLabs request failed ({response.status_code})' + suffix)


async def voices():
    global _voices
    if _voices is None:
        headers = {'xi-api-key': _key()}
        async with httpx.AsyncClient(timeout=20) as client:
            # Current endpoint first; the older v1 listing as a fallback.
            response = await client.get('https://api.elevenlabs.io/v2/voices', headers=headers, params={'page_size': 100})
            if response.status_code >= 400:
                legacy = await client.get(API + '/voices', headers=headers)
                if legacy.status_code < 400: response = legacy
        default = os.getenv('ELEVENLABS_VOICE_ID', '')
        if response.status_code >= 400 and default:
            # Listing not permitted, but a configured voice still lets voice work.
            return [{'voice_id': default, 'name': 'Default voice (from .env)'}]
        _check(response)
        _voices = sorted(({'voice_id': v['voice_id'], 'name': v.get('name') or 'Voice'}
                          for v in response.json().get('voices', []) if v.get('voice_id')), key=lambda v: v['name'].lower())
    return _voices


async def transcribe(data, mime):
    base = (mime or '').split(';')[0].strip().lower()
    ext = AUDIO_TYPES.get(base)
    if not ext: raise ValueError('Unsupported recording format.')
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('The recording could not be read.') from None
    if not raw or len(raw) > MAX_AUDIO: raise ValueError('The recording is empty or too long.')
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(API + '/speech-to-text', headers={'xi-api-key': _key()},
                                     data={'model_id': STT_MODEL}, files={'file': ('speech.' + ext, raw, base)})
    _check(response)
    usage_meter.log_voice('Voice input', STT_MODEL, {'bytes': len(raw)})
    return (response.json().get('text') or '').strip()


def speakable(text):
    """Strip Markdown and code so the voice reads prose, then cap the length at a sentence end."""
    text = re.sub(r'```.*?```', ' (code omitted) ', text, flags=re.S)
    text = re.sub(r'`([^`]*)`', r'\1', text)
    text = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'^\s{0,3}(#{1,6}|>|[-*+]|\d+\.)\s+', '', text, flags=re.M)
    text = re.sub(r'[*_~|]+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > MAX_SPEAK:
        cut = text[:MAX_SPEAK]
        end = max(cut.rfind('. '), cut.rfind('? '), cut.rfind('! '))
        text = (cut[:end + 1] if end > MAX_SPEAK // 2 else cut) + ' The rest is on screen.'
    return text


async def speak(text, voice_id):
    if not re.fullmatch(r'[A-Za-z0-9]{8,40}', voice_id or ''): raise ValueError('Choose a voice first.')
    clean = speakable(text)
    if not clean: raise ValueError('Nothing to read aloud.')
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(f'{API}/text-to-speech/{voice_id}',
                                     headers={'xi-api-key': _key(), 'accept': 'audio/mpeg'},
                                     json={'text': clean, 'model_id': TTS_MODEL})
    _check(response)
    usage_meter.log_voice('Voice output', TTS_MODEL, {'characters': len(clean)})
    return response.content
