from drellion.library import SoundLibrary
from drellion.exporter import PRESETS

def test_sound_library_scans_supported_files(tmp_path):
    (tmp_path/'kick.wav').write_bytes(b'RIFF')
    (tmp_path/'note.txt').write_text('x')
    lib=SoundLibrary(tmp_path)
    items=lib.scan()
    assert len(items)==1
    assert items[0].name=='kick'

def test_export_presets_cover_core_formats():
    for name in ('WAV','FLAC','MP3 320k','AAC/M4A','AIFF','OGG Vorbis','Opus'):
        assert name in PRESETS
