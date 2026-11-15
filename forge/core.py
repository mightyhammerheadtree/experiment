"""Non-executing PE inspection and explicit GEX build orchestration."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
import pefile

GEX_REV = '9004980758dbba3f16fa40db7dbc69cc4a9a2eb9'
MAX_EXE = 64 * 1024 * 1024


def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def inspect(path):
    path = Path(path)
    if path.stat().st_size > MAX_EXE:
        raise ValueError('EXE exceeds the 64 MiB inspection limit')
    data = path.read_bytes()
    try:
        pe = pefile.PE(data=data, fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT'], pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT']])
    except pefile.PEFormatError as e:
        raise ValueError(f'Invalid Windows PE: {e}') from e
    try:
        if len(pe.sections) > 96:
            raise ValueError('Unreasonable section count')
        sections = []
        for s in pe.sections:
            if s.PointerToRawData+s.SizeOfRawData > len(data):
                raise ValueError('Section extends beyond file')
            sections.append(dict(name=s.Name.rstrip(b'\0').decode('ascii','replace'), rva=s.VirtualAddress, virtual_size=s.Misc_VirtualSize, size=s.SizeOfRawData, offset=s.PointerToRawData, executable=bool(s.Characteristics & 0x20000000)))
        imports = sorted({e.dll.decode('ascii','replace') for table in ['DIRECTORY_ENTRY_IMPORT','DIRECTORY_ENTRY_DELAY_IMPORT'] for e in getattr(pe,table,[])})
        arch = {0x14c:'x86',0x8664:'x64',0xaa64:'arm64'}.get(pe.FILE_HEADER.Machine,'unknown')
        if (arch == 'x64' and pe.OPTIONAL_HEADER.Magic != 0x20b) or (arch == 'x86' and pe.OPTIONAL_HEADER.Magic != 0x10b):
            raise ValueError('PE machine and optional-header bitness disagree')
        siblings = sorted(p.name for p in path.parent.iterdir() if p.is_file() and not p.is_symlink())
        engine = 'GameMaker (data.win present)' if any(n.lower() == 'data.win' for n in siblings) else 'Unknown'
        blockers = ['No gameplay recording supplied; a runnable static build has not been produced.', 'Windows API, graphics, audio and code coverage must be validated in GEX/Wine.']
        if arch not in ('x64','x86'):
            blockers.append('Only x64 and x86 Windows targets are currently planned.')
        if any(x.lower() == 'mscoree.dll' for x in imports):
            blockers.append('Managed .NET executable: GEX Wine does not ship Mono.')
        return dict(schema=2, name=path.name, sha256=hashlib.sha256(data).hexdigest(), size=len(data), architecture=arch, image_base=hex(pe.OPTIONAL_HEADER.ImageBase), entry_rva=hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint), subsystem=pe.OPTIONAL_HEADER.Subsystem, dll=bool(pe.FILE_HEADER.Characteristics & 0x2000), sections=sections, imports=imports, engine=engine, companion_files=siblings, status='analysis-only', blockers=blockers, parser='pefile 2024.8.26', warnings=pe.get_warnings()[:30], gex_revision=GEX_REV)
    finally:
        pe.close()


def handoff(path, output, code=False, budget=100000):
    from .planning import plan
    report = plan(path, code, budget)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.resolve() == Path(path).resolve():
        raise ValueError('Output cannot overwrite the input executable')
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('report.json', json.dumps(report, indent=2))
        z.writestr('READ-ME-FIRST.txt', 'ANALYSIS ONLY — NOT A PLAYABLE PORT.\nNo EXE was executed or compiled.\nSee workflow.md for the real GEX recording/eject process.\n')
        z.write(Path(__file__).resolve().parent.parent/'docs/workflow.md', 'workflow.md')
    return report


def strict_settings(config):
    """The Wine page path uses features.translation, NOT generic jit_fallback."""
    config.setdefault('features', {})['translation'] = False
    config['cold'] = 'none'
    config['bundle'] = 'whole'
    config['resources'] = 'whole'
    config['helpers'] = 'keep'
    config.setdefault('start', {})['filesystem'] = 'memory'
    return config


def validate_launch(launch, expected_arch):
    if expected_arch not in ('x64', 'x86') or not isinstance(launch, dict):
        raise ValueError('Invalid target architecture or launch manifest')
    expected = 'wine64' if expected_arch == 'x64' else 'wine32'
    if launch.get('kind') != expected:
        raise ValueError(f'Expected {expected} launch, got {launch.get("kind")}')
    disabled = launch.get('features_off')
    if not isinstance(disabled, list) or 'translation' not in disabled:
        raise ValueError('Refusing export: runtime translation is not disabled')
    if not isinstance(launch.get('units'), list) or not launch['units']:
        raise ValueError('Refusing export with no compiled units')
    return True


def build(gex, recording, output, arch='x64', unit_cache=None):
    """Execute only trusted upstream tooling, never an uploaded command.

    A recording and prepared Wine bundle remain prerequisites. The legacy
    wine32-session.json filename is also used for upstream wine64 projects.
    """
    if arch not in ('x64','x86'):
        raise ValueError('Build target must be x64 or x86')
    gex, recording, output = map(lambda p: Path(p).resolve(), (gex, recording, output))
    if output.exists():
        raise ValueError('Output must not exist (build will not overwrite files)')
    session = recording/'wine32-session.json'
    if not session.is_file():
        raise ValueError('Requires a GEX wine32-session.json recording (used for both x64 and x86)')
    if not (gex/'target/x86/release/gexc').is_file():
        raise ValueError('Build GEX first; see docs/workflow.md and doctor output')
    revision = subprocess.check_output(['git', '-C', str(gex), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != GEX_REV:
        raise ValueError('GEX checkout does not match the audited pinned revision')
    from .preflight import preflight
    readiness = preflight(gex, recording, arch, unit_cache)
    if readiness['failures']:
        details = '; '.join(c['id']+': '+c['detail'] for c in readiness['checks'] if c['status'] == 'fail')
        raise ValueError('Build preflight blocked: '+details)
    output.mkdir(parents=True)
    (output/'preflight.json').write_text(json.dumps(readiness, indent=2))
    project, site = output/'project', output/'site'
    commands = []
    def run(cmd):
        commands.append(cmd)
        (output/'commands.json').write_text(json.dumps(commands, indent=2))
        subprocess.run(cmd, cwd=gex, check=True)
    command = [str(gex/'target/x86/release/gexc'), 'eject', str(recording), '--out', str(project), '--web-src', str(gex/'page')]
    if unit_cache:
        command += ['--unit-cache', str(Path(unit_cache).resolve())]
    run(command)
    model = json.loads((project/'gex-project.json').read_text())
    expected = 'wine64' if arch == 'x64' else 'wine32'
    if model.get('kind') != expected:
        raise ValueError(f'Recording ejected as {model.get("kind")}, expected {expected}')
    settings = project/'user/eject.json'
    settings.write_text(json.dumps(strict_settings(json.loads(settings.read_text())), indent=2))
    run(['bash', str(project/'build.sh')])
    launch = json.loads((project/'build/web/wine32.json').read_text())
    validate_launch(launch, arch)
    run(['node', str(gex/'site/eject-site.mjs'), str(project), str(site)])
    if not (site/'index.html').is_file() or not any(p.name.endswith(('.wasm','.wasm.zst')) for p in site.rglob('*')):
        raise ValueError('GEX output missing index.html or WebAssembly artifacts')
    summary = json.loads((site/'site.json').read_text())
    validate_launch(dict(summary, units=launch['units']), arch)
    manifest = dict(schema=1, status='built-not-gameplay-validated', architecture=arch, gex_revision=revision, strict_aot=True, runtime_translation=False, files={})
    for p in sorted(site.rglob('*')):
        if p.is_symlink():
            raise ValueError('Refusing symlink in site output')
        if p.is_file():
            manifest['files'][p.relative_to(site).as_posix()] = hash_file(p)
    (site/'glassforge-build.json').write_text(json.dumps(manifest, indent=2))
    archive = output/'browser-build.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(site.rglob('*')):
            if p.is_file(): z.write(p, p.relative_to(site))
    from .verify import verify
    verification = verify(archive)
    (output/'verification.json').write_text(json.dumps(verification, indent=2))
    if verification['status'] == 'invalid':
        archive.unlink()
        raise ValueError('Export integrity verification failed: '+ '; '.join(verification['errors']))
    return archive
