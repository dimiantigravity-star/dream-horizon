# Horizon 26.3 for Dream

Dream downloads `horizon-26.3.html`, keeps it in IndexedDB and opens it in its game frame. The HTML contains the single-threaded WebAssembly client. Chrome and Edge with WebGPU and WebAssembly JSPI can run it offline after downloading it.

On the first launch, choose `horizon-26.3-resources.tar` prepared from your own copy of Minecraft: Java Edition. The game stores the pack in your browser for subsequent launches. The pack is private and does not belong in this repository. The default pack includes English, Russian and sound effects.

## Building the download

The client uses [Horizon Web at `f02739c`](https://github.com/nobuildersnotools/horizon-web/tree/f02739c6996fe76321253543b782c1c53c53b93e), where the single-threaded build supports single-player. See the upstream [build instructions](https://github.com/nobuildersnotools/horizon-web/blob/f02739c6996fe76321253543b782c1c53c53b93e/web/README.md). With stable Rust, a WASM-capable Clang and `wasm-bindgen-cli` 0.2.129 installed, run `THREADS=0 BUNDLE=0 DIST=web/dist-st PROFILE=fast web/build.sh` in that checkout. Then run this repository's packager.

```sh
python package.py --source ../horizon-web --pkg ../horizon-web/web/dist-st/pkg
```

After preparing your own files with Horizon's `horizon-prepare`, create the private pack locally. The example below saves it outside this repository.

```sh
python package.py --source ../horizon-web \
  --resources ../horizon-web/.local/horizon-client/26.3 \
  --resource-tar ../horizon-26.3-resources.tar
```

Horizon is unofficial. Minecraft's game data, textures and sounds are separate from the open-source client. See [Horizon’s license](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md).
