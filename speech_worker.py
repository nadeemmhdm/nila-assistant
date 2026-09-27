"""Optional Piper subprocess protocol. No chat text/audio is written to disk."""
import base64
import io
import json
import sys
import wave
from piper import PiperVoice, SynthesisConfig


def main():
    voice = PiperVoice.load(sys.argv[1], use_cuda=False)
    config = SynthesisConfig(length_scale=1.0 / float(sys.argv[2]))
    print(json.dumps({'ready':True}), flush=True)
    for line in sys.stdin:
        try:
            data=json.loads(line)
            text=data['text']
            if not isinstance(text,str) or len(text)>1500: raise ValueError('Invalid speech chunk')
            audio=io.BytesIO()
            with wave.open(audio,'wb') as wav:
                voice.synthesize_wav(text,wav,syn_config=config)
            print(json.dumps({'wav':base64.b64encode(audio.getvalue()).decode('ascii')}),flush=True)
        except Exception:
            # Do not leak prompt text in exceptions or diagnostics.
            print(json.dumps({'error':'Speech synthesis failed for this voice/text.'}),flush=True)

if __name__=='__main__': main()
