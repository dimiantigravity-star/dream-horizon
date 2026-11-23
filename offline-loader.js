function resourceDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open('dream-horizon-resources', 1);
        request.onupgradeneeded = () => request.result.createObjectStore('packs');
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

function cachedPack(db) {
    return new Promise((resolve, reject) => {
        const request = db.transaction('packs').objectStore('packs').get('26.3');
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

function cachePack(db, file) {
    return new Promise((resolve, reject) => {
        const transaction = db.transaction('packs', 'readwrite');
        transaction.objectStore('packs').put(file, '26.3');
        transaction.oncomplete = resolve;
        transaction.onabort = () => reject(transaction.error);
    });
}

async function resourceParts(file) {
    const entries = new Map();
    const decoder = new TextDecoder();
    for (let offset = 0; offset + 512 <= file.size;) {
        const header = new Uint8Array(await file.slice(offset, offset + 512).arrayBuffer());
        if (!header[0]) break;
        const name = decoder.decode(header.subarray(0, 100)).split('\0')[0];
        const length = Number.parseInt(decoder.decode(header.subarray(124, 136)), 8);
        const data = offset + 512;
        if (!Number.isSafeInteger(length) || length < 0 || data + length > file.size || entries.has(name)) {
            throw new Error('Invalid resource archive');
        }
        entries.set(name, file.slice(data, data + length));
        offset = data + Math.ceil(length / 512) * 512;
    }
    const marker = entries.get('horizon-resources.json');
    const boot = entries.get('boot.tar.gz');
    const store = entries.get('store.gz');
    const manifest = entries.get('manifest.txt');
    if (!marker || !boot || !store || !manifest) throw new Error('Incomplete resource archive');
    const version = JSON.parse(await marker.text());
    if (version.minecraft !== '26.3' || version.schema !== 7) throw new Error('Wrong resource version');
    return {boot, store, manifest: await manifest.text()};
}

async function loadResourcePack() {
    const db = await resourceDB();
    try {
        const cached = await cachedPack(db);
        if (cached) {
            const parts = await resourceParts(cached).catch(() => null);
            if (parts) return parts;
        }
        const input = document.getElementById('horizon-resources');
        status.textContent = 'Selecciona horizon-26.3-resources.tar para jugar sin conexión.';
        input.hidden = false;
        for (;;) {
            const file = await new Promise(resolve => {
                input.addEventListener('change', () => resolve(input.files[0]), {once: true});
            });
            input.value = '';
            if (!file) continue;
            const parts = await resourceParts(file).catch(() => null);
            if (!parts) {
                status.textContent = 'Selecciona un paquete válido de Horizon 26.3 (.tar).';
                continue;
            }
            status.textContent = 'Guardando recursos para jugar sin conexión…';
            await cachePack(db, file);
            input.hidden = true;
            return parts;
        }
    } finally {
        db.close();
    }
}

globalThis.horizonOffline = async () => {
    if (typeof WebAssembly.Suspending !== 'function' || typeof WebAssembly.promising !== 'function') {
        throw new Error('Actualiza Chrome o Edge para ejecutar esta versión de Horizon.');
    }
    const resources = await loadResourcePack();
    status.textContent = 'Cargando Horizon…';
    const glue = await import(GLUE);
    await glue.default({module_or_path: await gunzip(held('horizon-wasm'))});
    const tar = await gunzip(resources.boot);
    const store = await gunzip(resources.store);
    const index = new Map();
    let offset = 0;
    for (const line of resources.manifest.split('\n')) {
        if (!line) continue;
        const [name, length] = line.split('\t');
        const end = offset + Number(length);
        if (!Number.isSafeInteger(end) || end < offset || end > store.length) throw new Error('Invalid resource manifest');
        index.set(name, [offset, end]);
        offset = end;
    }
    if (offset !== store.length) throw new Error('Incomplete resource data');
    globalThis.horizonHeldFile = url => {
        const range = url.startsWith('held:') && index.get(url.slice(5));
        return range ? store.subarray(...range) : undefined;
    };
    return {glue, tar, manifest: resources.manifest, base: 'held:'};
};
