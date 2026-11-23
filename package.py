"""Make Dream's downloadable Horizon HTML and a separate private resource tar."""

import argparse
import base64
import gzip
import importlib.util
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent


def upstream_package(source):
    sys.path.insert(0, str(source / 'web'))
    spec = importlib.util.spec_from_file_location('upstream_package', source / 'web/package.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resource_tar(upstream, resources, output):
    marker = resources / 'horizon-resources.json'
    version = json.loads(marker.read_text(encoding='utf-8'))
    if version['minecraft'] != '26.3' or version['schema'] != 7:
        raise ValueError('Expected prepared Horizon 26.3 resources (schema 7)')

    boot, lazy = [], []
    for file in sorted(resources.rglob('*')):
        relative = file.relative_to(resources)
        if not file.is_file() or relative.parts[0] in ('classes', 'client-classes') or file.suffix == '.log':
            continue
        name = relative.as_posix()
        if not upstream.bundle.lazy(name) or relative.parts[0] in upstream.bundle.PACKED_DIRS:
            boot.append((name, file))
        elif upstream.held(name, 'effects', False) or name == 'assets/minecraft/lang/ru_ru.json':
            lazy.append((name, file))

    with tempfile.TemporaryDirectory(dir=output.parent) as work:
        work = Path(work)
        with gzip.open(work / 'boot.tar.gz', 'wb', compresslevel=6) as bundle:
            with tarfile.open(fileobj=bundle, mode='w|', format=tarfile.GNU_FORMAT) as archive:
                for name, file in boot:
                    archive.add(file, arcname=name, recursive=False)
        with gzip.open(work / 'store.gz', 'wb', compresslevel=6) as bundle:
            for _, file in lazy:
                with file.open('rb') as stream:
                    shutil.copyfileobj(stream, bundle)
        (work / 'manifest.txt').write_text(''.join(f'{name}\t{file.stat().st_size}\n' for name, file in lazy), encoding='utf-8', newline='\n')
        with tarfile.open(output, 'w', format=tarfile.USTAR_FORMAT) as archive:
            archive.add(marker, arcname=marker.name)
            for name in ('boot.tar.gz', 'store.gz', 'manifest.txt'):
                archive.add(work / name, arcname=name)
    print(f'Private resources: {output.stat().st_size:,} bytes')


def remap_build_paths(wasm, checkout):
    # Rust panic locations carry byte lengths. Keep replacements the same length.
    for directory in (checkout, Path.home()):
        for path in {str(directory), directory.as_posix()}:
            prefix = path.encode('utf-8')
            replacement = b'/build'[:len(prefix)].ljust(len(prefix), b'/')
            wasm = wasm.replace(prefix, replacement)
    return wasm


def standalone_html(upstream, pkg, output):
    web = upstream.WEB
    page = (web / 'index.html').read_text(encoding='utf-8')
    main = (web / 'main.js').read_text(encoding='utf-8').replace('import "./audio.js";', '')
    main = main.split('    // The threaded build shares memory between workers,', 1)[0]
    main += '    status.textContent = `Horizon no pudo iniciarse:\\n${e}`;\n});\n'
    init, _, _ = upstream.OFFLINE_LOADER.partition('globalThis.horizonOffline =')
    engine = remap_build_paths((pkg / 'horizon-client_bg.wasm').read_bytes(), upstream.REPO)
    wasm = base64.b64encode(upstream.gz(engine)).decode()
    audio = (web / 'audio.js').read_text(encoding='utf-8')
    loader = (HERE / 'offline-loader.js').read_text(encoding='utf-8')
    head, tail = page.split('<script type="module" src="main.js"></script>')
    license_text = (HERE / 'LICENSE').read_text(encoding='utf-8')
    with output.open('w', encoding='utf-8', newline='\n') as html:
        html.write(head)
        html.write(f'<!--\n{license_text}-->\n')
        html.write('<input id="horizon-resources" type="file" accept=".tar" aria-label="Horizon 26.3 resources" hidden style="position:fixed;top:calc(50% + 3rem);left:50%;transform:translateX(-50%);z-index:5">\n')
        html.write(f'<script id="horizon-wasm" type="application/octet-stream">{wasm}</script>\n')
        html.write(f'<script>\n{audio}\n</script>\n<script type="module">\n')
        html.write(f'const GLUE = "{upstream.glue_url(pkg)}";\n{init}\n{loader}\n{main}\n</script>\n')
        html.write(tail)
    print(f'Downloadable HTML: {output.stat().st_size:,} bytes')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Pinned horizon-web checkout')
    parser.add_argument('--pkg', type=Path, help='Output from wasm-bindgen --target web')
    parser.add_argument('--html', type=Path, default=HERE / 'horizon-26.3.html')
    parser.add_argument('--resources', type=Path, help='Private prepared Minecraft folder')
    parser.add_argument('--resource-tar', type=Path, help='Private output path, outside this repository')
    args = parser.parse_args()
    if bool(args.resources) != bool(args.resource_tar):
        parser.error('--resources and --resource-tar are used together')
    if not (args.pkg or args.resources):
        parser.error('Choose at least one of --pkg and --resources')
    upstream = upstream_package(args.source.resolve())
    if args.pkg:
        standalone_html(upstream, args.pkg, args.html)
    if args.resources and args.resource_tar:
        if args.resource_tar.resolve().is_relative_to(HERE):
            parser.error('Keep the resource tar outside the distribution repository')
        resource_tar(upstream, args.resources, args.resource_tar)


if __name__ == '__main__':
    main()
