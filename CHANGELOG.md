# CHANGELOG

<!-- version list -->

## 1.12.1-rc.0 (2026-08-25)

### Bug Fixes

- title every registered tool and enforce it registry-wide (#353)

## 1.12.0 (2026-08-06)

### Features

- Reachable print-resolution output (resolution tier parameter) (#348)
  ([#348](https://github.com/pvliesdonk/image-generation-mcp/pull/348),
  [`0af4ed7`](https://github.com/pvliesdonk/image-generation-mcp/commit/0af4ed7bc0e3508c87bf3ea2944dde83ca5bb26b))


## 1.12.0-rc.1 (2026-07-10)

### Bug Fixes

- **gallery**: Bump galleryReqSeq on host reload + recover from cancelled loads (#322) (#328)
  ([#328](https://github.com/pvliesdonk/image-generation-mcp/pull/328),
  [`22c487f`](https://github.com/pvliesdonk/image-generation-mcp/commit/22c487f8d2142e5ce7553b26a4ba86e3758a796e))

### Documentation

- Reference-image ingestion narrative + LLM-facing tool hints (#310) (#326)
  ([#326](https://github.com/pvliesdonk/image-generation-mcp/pull/326),
  [`f022559`](https://github.com/pvliesdonk/image-generation-mcp/commit/f022559832040ea56192ada1d3772a7f8148182c))

### Features

- **gallery**: Filter gallery by image origin (generated/imported/all) (#318)
  ([#318](https://github.com/pvliesdonk/image-generation-mcp/pull/318),
  [`20c7511`](https://github.com/pvliesdonk/image-generation-mcp/commit/20c75112c71a01d0c67eda2ae3c6b7a40c5036cd))

- **gallery**: Imported-image foundation — origin field + register_imported_image (#311)
  ([#311](https://github.com/pvliesdonk/image-generation-mcp/pull/311),
  [`d3a58af`](https://github.com/pvliesdonk/image-generation-mcp/commit/d3a58afde0664c0fe421f589901c7c8b5b606dad))

- **gallery**: Load-error state + segmented-control ARIA (#317, #319) (#321)
  ([#321](https://github.com/pvliesdonk/image-generation-mcp/pull/321),
  [`6f8d55e`](https://github.com/pvliesdonk/image-generation-mcp/commit/6f8d55e07352a08a379f9b6b6983dca06e8679a2))

- **gallery**: Radiogroup keyboard nav for the origin control (#320) (#327)
  ([#327](https://github.com/pvliesdonk/image-generation-mcp/pull/327),
  [`2c957c7`](https://github.com/pvliesdonk/image-generation-mcp/commit/2c957c72c67e44f5472d4f239c209c36d537cf56))

- **tools**: Fetch_image — SSRF-hardened URL → gallery via fetch_url (closes #308) (#314)
  ([#314](https://github.com/pvliesdonk/image-generation-mcp/pull/314),
  [`90c96b9`](https://github.com/pvliesdonk/image-generation-mcp/commit/90c96b9db341412b25b1dc74775d8dfcdd2f3f65))

- **tools**: Ingest_base64_image — inline base64 → gallery via decode_base64_capped (closes #309)
  (#316) ([#316](https://github.com/pvliesdonk/image-generation-mcp/pull/316),
  [`e410a35`](https://github.com/pvliesdonk/image-generation-mcp/commit/e410a3537392cba9868066a8972fc71c504a226e))

- **transfer**: Adopt pvl-core register_transfer_routes; retire artifacts.py (closes #307, #220)
  (#312) ([#312](https://github.com/pvliesdonk/image-generation-mcp/pull/312),
  [`f608fad`](https://github.com/pvliesdonk/image-generation-mcp/commit/f608fadaacae337d96d8b8fcec210cfaf61b7e24))


## 1.11.0 (2026-07-04)

### Bug Fixes

- **ci**: Vale Docs Prose passing baseline (#244) (#270)
  ([#270](https://github.com/pvliesdonk/image-generation-mcp/pull/270),
  [`a547a63`](https://github.com/pvliesdonk/image-generation-mcp/commit/a547a63d8cbe4ebfb964bc5ed1341e8c548f9c48))

### Chores

- Add gitleaks pre-commit + restore vendor_spa.py (closes #278) (#285)
  ([#285](https://github.com/pvliesdonk/image-generation-mcp/pull/285),
  [`da586dd`](https://github.com/pvliesdonk/image-generation-mcp/commit/da586dd67b9ce213dc2820f4b4a0e89626bf79da))

- **copier**: Update template v2.5.3 → v2.6.0 (conflicts + lock) [red until wizard PR] (#286)
  ([#286](https://github.com/pvliesdonk/image-generation-mcp/pull/286),
  [`8957b1a`](https://github.com/pvliesdonk/image-generation-mcp/commit/8957b1a4ce5ff5db46f7167a676c00f9f2dbdf03))

- **copier**: Update template v2.6.0 → v2.10.2 (#299)
  ([#299](https://github.com/pvliesdonk/image-generation-mcp/pull/299),
  [`2e07a46`](https://github.com/pvliesdonk/image-generation-mcp/commit/2e07a468708acd880dbc35671316a633f24e3b28))

- **copier**: Update to v2.5.3 (#254)
  ([#254](https://github.com/pvliesdonk/image-generation-mcp/pull/254),
  [`1decabb`](https://github.com/pvliesdonk/image-generation-mcp/commit/1decabb688ac66df88c63c34ccad57f057ecac70))

- **deps**: Bump pip from 26.0.1 to 26.1 (#224)
  ([#224](https://github.com/pvliesdonk/image-generation-mcp/pull/224),
  [`2b8f0ca`](https://github.com/pvliesdonk/image-generation-mcp/commit/2b8f0caa12962c66e9cb4169247e3a648b95b624))

- **template**: Apply copier template v2.2.1 (#250)
  ([#250](https://github.com/pvliesdonk/image-generation-mcp/pull/250),
  [`9589fe9`](https://github.com/pvliesdonk/image-generation-mcp/commit/9589fe9cf54e485557b298155287967ffa721b33))

- **template**: Apply copier template v2.3.0 (#253)
  ([#253](https://github.com/pvliesdonk/image-generation-mcp/pull/253),
  [`a727a9e`](https://github.com/pvliesdonk/image-generation-mcp/commit/a727a9ef10f2bd8779ac9393f73a4bc30182662d))

### Documentation

- Correct PAID_PROVIDERS default in README (openai, not openai,gemini) (#272)
  ([#272](https://github.com/pvliesdonk/image-generation-mcp/pull/272),
  [`5281e56`](https://github.com/pvliesdonk/image-generation-mcp/commit/5281e56fe4440b7a09c8415b175e42aca084000f))

- Reference-image input closeout + prompt guidance (#262) (#269)
  ([#269](https://github.com/pvliesdonk/image-generation-mcp/pull/269),
  [`2ae9af6`](https://github.com/pvliesdonk/image-generation-mcp/commit/2ae9af6b22ad7fae1c60330d546aca0d791cb073))

### Features

- Gemini multi-image composition (#260) (#267)
  ([#267](https://github.com/pvliesdonk/image-generation-mcp/pull/267),
  [`17e9ffc`](https://github.com/pvliesdonk/image-generation-mcp/commit/17e9ffc78b17f6641becbb6844ae1a0a3587cb97))

- OpenAI gpt-image image editing and composition (#258) (#265)
  ([#265](https://github.com/pvliesdonk/image-generation-mcp/pull/265),
  [`0939c46`](https://github.com/pvliesdonk/image-generation-mcp/commit/0939c460618b1fd39e4a90076faa8db053523e77))

- OpenAI inpainting masks (#261) (#268)
  ([#268](https://github.com/pvliesdonk/image-generation-mcp/pull/268),
  [`3225161`](https://github.com/pvliesdonk/image-generation-mcp/commit/32251611f0d0c643b615178b21edf3699cf01db9))

- Reference-image input — foundation + Gemini single-image i2i (#257) (#263)
  ([#263](https://github.com/pvliesdonk/image-generation-mcp/pull/263),
  [`dac4dbd`](https://github.com/pvliesdonk/image-generation-mcp/commit/dac4dbdb17625435e5248878eceb65e8a706287b))

- SD WebUI img2img + denoising strength (#259) (#266)
  ([#266](https://github.com/pvliesdonk/image-generation-mcp/pull/266),
  [`a5bcb88`](https://github.com/pvliesdonk/image-generation-mcp/commit/a5bcb8820194748bb7048cb97ed4b6f849a3b15f))

- **providers**: Refresh image-model catalog for current OpenAI + Gemini models (#294)
  ([#294](https://github.com/pvliesdonk/image-generation-mcp/pull/294),
  [`f9761b3`](https://github.com/pvliesdonk/image-generation-mcp/commit/f9761b3613ac082e5cfc996a396a5bdf379df9c4))

### Refactoring

- Rename domain modules to template scaffold layout (#282)
  ([#282](https://github.com/pvliesdonk/image-generation-mcp/pull/282),
  [`6fcb15a`](https://github.com/pvliesdonk/image-generation-mcp/commit/6fcb15aae14930340f3efea0cdfc2cc8c28396a1))

- **cli**: De-fork CLI to stock typer; drop non-canonical HTTP logging middleware (#281)
  ([#281](https://github.com/pvliesdonk/image-generation-mcp/pull/281),
  [`f73fb57`](https://github.com/pvliesdonk/image-generation-mcp/commit/f73fb575e7bc5a9c653e870aafb0bba7e998d487))

- **config**: Adopt ProjectConfig.from_env() classmethod (replaces load_config) (#280)
  ([#280](https://github.com/pvliesdonk/image-generation-mcp/pull/280),
  [`4f19311`](https://github.com/pvliesdonk/image-generation-mcp/commit/4f19311e9136058e1ef5db96b76c2a9ad4f42d98))

- **server**: Restore template server_lifespan; remove orphaned build_event_store (closes #276)
  (#283) ([#283](https://github.com/pvliesdonk/image-generation-mcp/pull/283),
  [`363c73c`](https://github.com/pvliesdonk/image-generation-mcp/commit/363c73c69dcddc4b959147c1c03763ac42aebb22))

### Testing

- Add template client fixture + smoke coverage (closes #277) (#284)
  ([#284](https://github.com/pvliesdonk/image-generation-mcp/pull/284),
  [`08b7c84`](https://github.com/pvliesdonk/image-generation-mcp/commit/08b7c84e593148f5cf78c909b01f455c0ae4d79d))


## 1.10.1 (2026-06-18)

### Bug Fixes

- **wizard**: Correct .cfg-warn → .cfg-warning CSS class; drop stale CVE suppression (#248)
  ([#248](https://github.com/pvliesdonk/image-generation-mcp/pull/248),
  [`cac1b90`](https://github.com/pvliesdonk/image-generation-mcp/commit/cac1b9076f3d91d8f7699453671413a4d6828fa1))

### Chores

- **template**: Apply copier template v2.1.1 → v2.2.0 (#246)
  ([#246](https://github.com/pvliesdonk/image-generation-mcp/pull/246),
  [`62941f7`](https://github.com/pvliesdonk/image-generation-mcp/commit/62941f7048458256118543a968a3249154510284))


## 1.10.0 (2026-06-18)


## 1.10.0-rc.1 (2026-06-18)

### Chores

- Add .gemini/config.yaml to scope gemini-code-assist as a one-pass gate (#218)
  ([#218](https://github.com/pvliesdonk/image-generation-mcp/pull/218),
  [`81043de`](https://github.com/pvliesdonk/image-generation-mcp/commit/81043de664b8bd45c17e5ba99f00c30f311565b1))

- **copier**: Update to v1.2.0 (#201)
  ([#201](https://github.com/pvliesdonk/image-generation-mcp/pull/201),
  [`5515e04`](https://github.com/pvliesdonk/image-generation-mcp/commit/5515e04ccb8d4bc1912131d683a1587990ea496d))

- **copier**: Update to v1.2.1 (#216)
  ([#216](https://github.com/pvliesdonk/image-generation-mcp/pull/216),
  [`4e7ce3c`](https://github.com/pvliesdonk/image-generation-mcp/commit/4e7ce3c58104e09eb786c2c0d2ea7e1cfb647f3d))

- **deps**: Bulk dependency upgrade — supersedes dependabot #225–#238 (#239)
  ([#239](https://github.com/pvliesdonk/image-generation-mcp/pull/239),
  [`e4a7a37`](https://github.com/pvliesdonk/image-generation-mcp/commit/e4a7a379546514d45a5fba536370d660def2d5c7))

- **deps**: Consolidated uv.lock bump (cryptography, python-multipart, self-version) (#211)
  ([#211](https://github.com/pvliesdonk/image-generation-mcp/pull/211),
  [`41fc447`](https://github.com/pvliesdonk/image-generation-mcp/commit/41fc447adaacf9452b3f4b15508faabb0329c8d7))

- **pyproject**: Rename ruff TCH → TC in select for consistency (#209)
  ([#209](https://github.com/pvliesdonk/image-generation-mcp/pull/209),
  [`fe52139`](https://github.com/pvliesdonk/image-generation-mcp/commit/fe521393e2e526d5da879d0ab9cecfa5286a51ab))

- **template**: Apply copier template v1.2.1 → v2.1.1 (#243)
  ([#243](https://github.com/pvliesdonk/image-generation-mcp/pull/243),
  [`f698f2e`](https://github.com/pvliesdonk/image-generation-mcp/commit/f698f2e9fe50fb793735228d8907cafe94eb5f2b))

### Documentation

- **styles**: Refresh provider list + clarify style_profile vs style library (#215)
  ([#215](https://github.com/pvliesdonk/image-generation-mcp/pull/215),
  [`80eac2f`](https://github.com/pvliesdonk/image-generation-mcp/commit/80eac2f9f615b59a9283e28e8e706552a554a0e1))

### Features

- **deps**: Bump fastmcp-pvl-core to v3.x line (>=3.2.0,<4) (#242)
  ([#242](https://github.com/pvliesdonk/image-generation-mcp/pull/242),
  [`5d971f2`](https://github.com/pvliesdonk/image-generation-mcp/commit/5d971f2406e880471c2051551b87647f3a060888))

- **file-exchange**: Migrate to fastmcp_pvl_core register_file_exchange (#221)
  ([#221](https://github.com/pvliesdonk/image-generation-mcp/pull/221),
  [`b5727a1`](https://github.com/pvliesdonk/image-generation-mcp/commit/b5727a10f381059355432968c7cc83e8a89cfcff))

- **gemini**: Surface SynthID watermark capability on gemini-2.5-flash-image (#214)
  ([#214](https://github.com/pvliesdonk/image-generation-mcp/pull/214),
  [`21fcbfe`](https://github.com/pvliesdonk/image-generation-mcp/commit/21fcbfe1cb1ff69607938fba5d16fc0d54efffe3))

- **openai**: Add gpt-image-2 to provider config + registry (#213)
  ([#213](https://github.com/pvliesdonk/image-generation-mcp/pull/213),
  [`aabf786`](https://github.com/pvliesdonk/image-generation-mcp/commit/aabf786be95ac0ce6ba8f6809f3e0db77684ac59))

### Refactoring

- **prompts**: Refresh _SELECT_PROVIDER_PROMPT and prompt guides for 2026 model lineup (#212)
  ([#212](https://github.com/pvliesdonk/image-generation-mcp/pull/212),
  [`7592488`](https://github.com/pvliesdonk/image-generation-mcp/commit/7592488844cddb5ebeab487d903e2abaaa579649))


## 1.9.0 (2026-04-29)

### Features

- Per-model style metadata + warnings on list_providers (#207)
  ([#207](https://github.com/pvliesdonk/image-generation-mcp/pull/207),
  [`00e12a8`](https://github.com/pvliesdonk/image-generation-mcp/commit/00e12a8d3326fa08ff1891d4e0f539051dbfd036))


## 1.8.1 (2026-04-23)

### Bug Fixes

- **ci**: Stage conflict markers before git checkout -B in copier-update (#197)
  ([#197](https://github.com/pvliesdonk/image-generation-mcp/pull/197),
  [`21a3546`](https://github.com/pvliesdonk/image-generation-mcp/commit/21a3546c3cd270aaf3f854058df116d719cf0258))

- **gitignore**: Narrow .claude/ → specific per-user paths + add .worktrees/ (#189)
  ([#189](https://github.com/pvliesdonk/image-generation-mcp/pull/189),
  [`9f42d8b`](https://github.com/pvliesdonk/image-generation-mcp/commit/9f42d8bda0d9ee85c62c83c61c4c0191bf91e0b6))

### Chores

- **copier**: Converge drifted template-owned files to v1.1.5 shape (#196)
  ([#196](https://github.com/pvliesdonk/image-generation-mcp/pull/196),
  [`ee9a39f`](https://github.com/pvliesdonk/image-generation-mcp/commit/ee9a39f5ae253c2810494e049b458d95d6e34523))

- **copier**: Heavy backfill v1.0.0 → v1.1.1 + bootstrap copier-update workflow (#191)
  ([#191](https://github.com/pvliesdonk/image-generation-mcp/pull/191),
  [`55eb88e`](https://github.com/pvliesdonk/image-generation-mcp/commit/55eb88ebc0d3e0e0b91a8535c23adb8a36f5ffeb))

- **copier**: Update to v1.1.3 (#192)
  ([#192](https://github.com/pvliesdonk/image-generation-mcp/pull/192),
  [`7c04f30`](https://github.com/pvliesdonk/image-generation-mcp/commit/7c04f30ff47626a27455e381e4f5a19fe387d646))

- **copier**: Update to v1.1.4 (#193)
  ([#193](https://github.com/pvliesdonk/image-generation-mcp/pull/193),
  [`b4b90a0`](https://github.com/pvliesdonk/image-generation-mcp/commit/b4b90a078de4e166b49280a8c75e7a02185a5190))

- **copier**: Update to v1.1.8 (#198)
  ([#198](https://github.com/pvliesdonk/image-generation-mcp/pull/198),
  [`bfba50c`](https://github.com/pvliesdonk/image-generation-mcp/commit/bfba50c22e879787491a80f898db799f29ce0cdd))

### Refactoring

- **claude-md**: Add DOMAIN + TEMPLATE-OWNED sentinel structure (#195)
  ([#195](https://github.com/pvliesdonk/image-generation-mcp/pull/195),
  [`37f53d3`](https://github.com/pvliesdonk/image-generation-mcp/commit/37f53d3edd749944d782eb37b7f464906c59ef39))


## 1.8.0 (2026-04-21)


## 1.7.0-rc.2 (2026-04-21)

### Chores

- **deps**: Bump pygments from 2.19.2 to 2.20.0 (#157)
  ([#157](https://github.com/pvliesdonk/image-generation-mcp/pull/157),
  [`eebef07`](https://github.com/pvliesdonk/image-generation-mcp/commit/eebef07c0d7bc003d1836e400ffb49fad0981541))

- **deps**: Drop redundant httpx + uvicorn deps (#188)
  ([#188](https://github.com/pvliesdonk/image-generation-mcp/pull/188),
  [`97f566b`](https://github.com/pvliesdonk/image-generation-mcp/commit/97f566ba06f11b18296f52fbe6073bb0997b17be))


## 1.5.1 (2026-04-21)

### Bug Fixes

- **ci**: Docs concurrency collision on release + document tag-push intent (#186)
  ([#186](https://github.com/pvliesdonk/image-generation-mcp/pull/186),
  [`f525258`](https://github.com/pvliesdonk/image-generation-mcp/commit/f52525832fbf5e5b988391e6dfaa88811527bceb))

- **ci**: Trigger docs workflow on v* tag pushes (#185)
  ([#185](https://github.com/pvliesdonk/image-generation-mcp/pull/185),
  [`9f28b5a`](https://github.com/pvliesdonk/image-generation-mcp/commit/9f28b5a0a0a7d2b647450b234af4c503bbea8646))


## 1.7.0-rc.1 (2026-04-21)

### Bug Fixes

- **packaging**: Add mcpb bundle files (unblocks rc) (#184)
  ([#184](https://github.com/pvliesdonk/image-generation-mcp/pull/184),
  [`0008d24`](https://github.com/pvliesdonk/image-generation-mcp/commit/0008d24330f96cfe65778ac16309a22ea5f5ca27))


## 1.6.0-rc.1 (2026-04-21)

### Chores

- Adopt fastmcp-server-template v1.0.0 + fastmcp-pvl-core (#175)
  ([#175](https://github.com/pvliesdonk/image-generation-mcp/pull/175),
  [`e313d75`](https://github.com/pvliesdonk/image-generation-mcp/commit/e313d757cb4f5383c6b4b6f5203dd0b4ca2bd257))

- Update server.json to v1.5.0 [skip ci]
  ([`1d24411`](https://github.com/pvliesdonk/image-generation-mcp/commit/1d24411d5d9cfb0d39c6701e323c1a22d525f3ba))


## 1.5.0 (2026-04-01)

### Chores

- Update server.json to v1.4.0 [skip ci]
  ([`e551b01`](https://github.com/pvliesdonk/image-generation-mcp/commit/e551b01f2becbec5b4a3764a0b6a438c11501a52))

- **deps**: Bump fastmcp from 3.1.1 to 3.2.0 (#166)
  ([#166](https://github.com/pvliesdonk/image-generation-mcp/pull/166),
  [`8a98e85`](https://github.com/pvliesdonk/image-generation-mcp/commit/8a98e852e617628787264bfa031b05411e3e3b09))

- **deps**: Bump requests from 2.32.5 to 2.33.0 (#155)
  ([#155](https://github.com/pvliesdonk/image-generation-mcp/pull/155),
  [`7ef4557`](https://github.com/pvliesdonk/image-generation-mcp/commit/7ef45574d67165e69fe0992af99023a61bdc64f0))

### Documentation

- Fix prompts.md intro to count all three prompts (#163)
  ([#163](https://github.com/pvliesdonk/image-generation-mcp/pull/163),
  [`a205f03`](https://github.com/pvliesdonk/image-generation-mcp/commit/a205f038f0918731d24603288d51f525ab4fd41a))

- Update provider selection with live test findings (#167)
  ([#167](https://github.com/pvliesdonk/image-generation-mcp/pull/167),
  [`cd1ce26`](https://github.com/pvliesdonk/image-generation-mcp/commit/cd1ce262dfd2138c003c84b9afe6621655b0cad9))

### Features

- Add check_generation_status tool to avoid polling UI clutter (#161)
  ([#161](https://github.com/pvliesdonk/image-generation-mcp/pull/161),
  [`3065742`](https://github.com/pvliesdonk/image-generation-mcp/commit/306574217991987cd5240e8bc8357b89fc308e28))

- Gemini image generation provider (#160)
  ([#160](https://github.com/pvliesdonk/image-generation-mcp/pull/160),
  [`f4b463c`](https://github.com/pvliesdonk/image-generation-mcp/commit/f4b463c6d23323013fec75a1ea11862d5b326d58))

- Image transforms (crop/rotate/flip) + interactive editor (#156)
  ([#156](https://github.com/pvliesdonk/image-generation-mcp/pull/156),
  [`a621d12`](https://github.com/pvliesdonk/image-generation-mcp/commit/a621d12a302688044f06229e72064a15bdd9f83a))

- Wire up quality parameter to real API behavior (Gemini + OpenAI) (#165)
  ([#165](https://github.com/pvliesdonk/image-generation-mcp/pull/165),
  [`6031224`](https://github.com/pvliesdonk/image-generation-mcp/commit/60312246ec7e3089b45b386f79ad102e89900b8d))

### Performance Improvements

- Bundle ext-apps SDK to eliminate CDN dependency (#153)
  ([#153](https://github.com/pvliesdonk/image-generation-mcp/pull/153),
  [`e3c030e`](https://github.com/pvliesdonk/image-generation-mcp/commit/e3c030eca6a6728d0a3ed7e15ee8ce895130f936))


## 1.4.0 (2026-03-25)

### Bug Fixes

- Address architect-reviewer findings
  ([`aa1cb25`](https://github.com/pvliesdonk/image-generation-mcp/commit/aa1cb2517dfd96dbd8b1f614a6000f219092611a))

- Improve critical LLM-facing tool descriptions (#146)
  ([#146](https://github.com/pvliesdonk/image-generation-mcp/pull/146),
  [`6eb63cb`](https://github.com/pvliesdonk/image-generation-mcp/commit/6eb63cbe8cf0dc1ad0482d65ea261b1b057baefa))

- Polish secondary LLM-facing descriptions (#147)
  ([#147](https://github.com/pvliesdonk/image-generation-mcp/pull/147),
  [`aab9e79`](https://github.com/pvliesdonk/image-generation-mcp/commit/aab9e790437f568dbdffea42a303fd664cbe7fde))

- **ci**: Ignore CVE-2026-4539 in pip-audit (pygments, no fix available)
  ([`7e00d98`](https://github.com/pvliesdonk/image-generation-mcp/commit/7e00d98cd7f2e62a80278e466d7464f5051a9e02))

- **gallery**: Disable autoResize, use sendSizeChanged for frame height (#148)
  ([#148](https://github.com/pvliesdonk/image-generation-mcp/pull/148),
  [`1d08f31`](https://github.com/pvliesdonk/image-generation-mcp/commit/1d08f31c06f1a40c453ae3edcc3128501288aafd))

- **gallery**: Update callServerTool to {name,arguments} API, bump ext-apps to 1.3.1 (#140)
  ([#140](https://github.com/pvliesdonk/image-generation-mcp/pull/140),
  [`3516b77`](https://github.com/pvliesdonk/image-generation-mcp/commit/3516b77680b020cda681dfffc73ccbb82e6990c4))

- **widget**: Auto-compute Claude sandbox domain from BASE_URL
  ([`e0c69e3`](https://github.com/pvliesdonk/image-generation-mcp/commit/e0c69e32469811654115be3fcc39208b02a14897))

- **widget**: Correct LRU eviction order and restore console.warn (#132)
  ([#132](https://github.com/pvliesdonk/image-generation-mcp/pull/132),
  [`de990fa`](https://github.com/pvliesdonk/image-generation-mcp/commit/de990fa8823b7258918ffaf885e9905034359f74))

- **widget**: Derive MCP Apps domain from BASE_URL hostname (#127)
  ([#127](https://github.com/pvliesdonk/image-generation-mcp/pull/127),
  [`9f5c5d9`](https://github.com/pvliesdonk/image-generation-mcp/commit/9f5c5d928993a6ea5fde477bd3e043112f9cfeee))

- **widget**: Drop host-specific domain, use APP_DOMAIN env var
  ([`9922d7d`](https://github.com/pvliesdonk/image-generation-mcp/commit/9922d7dd0c54867aeea423bea8aad58a229a9592))

### Chores

- Update server.json to v1.3.0 [skip ci]
  ([`1a41d8f`](https://github.com/pvliesdonk/image-generation-mcp/commit/1a41d8f66b442e1af20b9843cc3747cb13e0e0a1))

### Documentation

- Add APP_DOMAIN env var and Claude hash computation
  ([`d8a4f24`](https://github.com/pvliesdonk/image-generation-mcp/commit/d8a4f246a83b103a8859a358fdb7fc9ce0a25e1e))

### Features

- Add server-level palette icon for MCP client UIs (#149)
  ([#149](https://github.com/pvliesdonk/image-generation-mcp/pull/149),
  [`a64e57e`](https://github.com/pvliesdonk/image-generation-mcp/commit/a64e57e8f47d0ae3d82765a2c285f46edbbfcf24))

- **gallery**: Add browse_gallery tool, gallery_page app-only tool, and gallery HTML resource (#133)
  ([#133](https://github.com/pvliesdonk/image-generation-mcp/pull/133),
  [`733b45f`](https://github.com/pvliesdonk/image-generation-mcp/commit/733b45fab9fa9701a30bbc6756c3c9cc6647cbce))

- **gallery**: Add delete_image tool and gallery delete buttons (#135)
  ([#135](https://github.com/pvliesdonk/image-generation-mcp/pull/135),
  [`68e20ea`](https://github.com/pvliesdonk/image-generation-mcp/commit/68e20ea632aa34b617b3d624fdcdb4e595b6d96e))

- **gallery**: Add lightbox zoom view and gallery_full_image app-only tool (#134)
  ([#134](https://github.com/pvliesdonk/image-generation-mcp/pull/134),
  [`2c9fab0`](https://github.com/pvliesdonk/image-generation-mcp/commit/2c9fab0e173a6fdbc767dcbe5eae7817e2d824f3))

- **gallery**: Add picture-in-picture (PiP) display mode (#142)
  ([#142](https://github.com/pvliesdonk/image-generation-mcp/pull/142),
  [`cdbbe3b`](https://github.com/pvliesdonk/image-generation-mcp/commit/cdbbe3ba53c450a0ec51df458f368f9940bc5d99))

- **http**: Add JSON-RPC-aware request logging middleware
  ([`5711c18`](https://github.com/pvliesdonk/image-generation-mcp/commit/5711c187e213b809e8f7b3097c3658f804d5f633))

- **http**: Add persistent EventStore for HTTP session resumability (#138)
  ([#138](https://github.com/pvliesdonk/image-generation-mcp/pull/138),
  [`27f181f`](https://github.com/pvliesdonk/image-generation-mcp/commit/27f181f24bdc884aa0145c5b23b3950ed7b66fb5))

- **http**: Log clientInfo, resource URIs, and User-Agent
  ([`7d28114`](https://github.com/pvliesdonk/image-generation-mcp/commit/7d28114ae05252aebc228c9c846bcfcbb4018072))

- **widget**: Add download button via ext-apps downloadFile API
  ([`8261f26`](https://github.com/pvliesdonk/image-generation-mcp/commit/8261f265ef5669bef0a6b64193399c98d088ec6a))

- **widget**: Redesign image viewer following ext-apps SDK patterns
  ([`fc2028c`](https://github.com/pvliesdonk/image-generation-mcp/commit/fc2028c2086935a0f7e46681d7a6a49820615fee))

- **widget**: Redesign MCP Apps image viewer with ext-apps SDK (#128)
  ([#128](https://github.com/pvliesdonk/image-generation-mcp/pull/128),
  [`213e058`](https://github.com/pvliesdonk/image-generation-mcp/commit/213e05887b6537a812dd42b265848cc79deb4e49))

- **widget**: Show generating/failed status instead of empty frame
  ([`5cf6a21`](https://github.com/pvliesdonk/image-generation-mcp/commit/5cf6a21cdcade993d46e1f47966cb696f636b79e))


## 1.3.0 (2026-03-24)

### Bug Fixes

- Add Flux prompt guidance and prompt_style metadata (#114) (#115)
  ([#115](https://github.com/pvliesdonk/image-generation-mcp/pull/115),
  [`546bc04`](https://github.com/pvliesdonk/image-generation-mcp/commit/546bc0482a0cd19e5df028b752cee700f33bd27a))

- Add force_refresh and refreshed_at to list_providers (#113) (#116)
  ([#116](https://github.com/pvliesdonk/image-generation-mcp/pull/116),
  [`e8e0478`](https://github.com/pvliesdonk/image-generation-mcp/commit/e8e0478d78d8a6a1dbf6cb53cfdc9a793f633179))

- Add MCP tool annotations and widget domain for ChatGPT compatibility (#121)
  ([#121](https://github.com/pvliesdonk/image-generation-mcp/pull/121),
  [`f23a8cf`](https://github.com/pvliesdonk/image-generation-mcp/commit/f23a8cfce7e149850f5807ecdb1fc6dca4aa6295))

- Set project GitHub URL as widget domain for ChatGPT app identity (#125)
  ([#125](https://github.com/pvliesdonk/image-generation-mcp/pull/125),
  [`72c0981`](https://github.com/pvliesdonk/image-generation-mcp/commit/72c098135d03406eb5808b35c90638d761686bde))

- Shorten server.json description for MCP registry 100-char limit (#103)
  ([#103](https://github.com/pvliesdonk/image-generation-mcp/pull/103),
  [`79ee6d0`](https://github.com/pvliesdonk/image-generation-mcp/commit/79ee6d042bb359c2560957aca63fce18882fdb3e))

- **widget**: Remove non-functional download button from image viewer (#123)
  ([#123](https://github.com/pvliesdonk/image-generation-mcp/pull/123),
  [`f5ca2a9`](https://github.com/pvliesdonk/image-generation-mcp/commit/f5ca2a94d8e16a636e82403db4771c8e4fb8a7ef))

### Chores

- Adopt shared infrastructure improvements from markdown-vault-mcp (#111)
  ([#111](https://github.com/pvliesdonk/image-generation-mcp/pull/111),
  [`d2c6956`](https://github.com/pvliesdonk/image-generation-mcp/commit/d2c695617fda1d1f3998d3b6d740c322b711edf2))

- Update server.json to v1.2.0 [skip ci]
  ([`b4a4bf8`](https://github.com/pvliesdonk/image-generation-mcp/commit/b4a4bf8cff294be3731875d474b980122d2517f7))

### Documentation

- Update Authelia setup for remote auth mode and Claude Code client config (#105)
  ([#105](https://github.com/pvliesdonk/image-generation-mcp/pull/105),
  [`a9e582f`](https://github.com/pvliesdonk/image-generation-mcp/commit/a9e582f8a65fe6e4221241493b27eb40528e2dac))

### Features

- Fire-and-forget async generation (#112) (#117)
  ([#117](https://github.com/pvliesdonk/image-generation-mcp/pull/117),
  [`fa6f661`](https://github.com/pvliesdonk/image-generation-mcp/commit/fa6f661ba849028f21f055b0be9cccdcb90151f2))

- **sd_webui**: Add Flux dev/schnell model presets (#109)
  ([#109](https://github.com/pvliesdonk/image-generation-mcp/pull/109),
  [`b05128b`](https://github.com/pvliesdonk/image-generation-mcp/commit/b05128b46af833dfd7b359bdd57297792c1f03a4))

- **sd_webui**: Add progress polling via /sdapi/v1/progress (#76) (#118)
  ([#118](https://github.com/pvliesdonk/image-generation-mcp/pull/118),
  [`434fea3`](https://github.com/pvliesdonk/image-generation-mcp/commit/434fea38d5c276258b3299fe0d728d605a992bbe))

### Refactoring

- Rename a1111 provider to sd-webui (#108)
  ([#108](https://github.com/pvliesdonk/image-generation-mcp/pull/108),
  [`2c389ff`](https://github.com/pvliesdonk/image-generation-mcp/commit/2c389ff23489c13556a50722ec1ac4eab649d82c))


## 1.2.0 (2026-03-22)

### Bug Fixes

- Add MCP-level keepalives during image generation to prevent client timeouts (#95) (#96)
  ([#96](https://github.com/pvliesdonk/image-generation-mcp/pull/96),
  [`3f6a91c`](https://github.com/pvliesdonk/image-generation-mcp/commit/3f6a91cd6a75931e95e0a17898b58266ca4387bf))

- Release pipeline failures in publish-linux-packages and publish-registry (#97) (#98)
  ([#98](https://github.com/pvliesdonk/image-generation-mcp/pull/98),
  [`cdf9c60`](https://github.com/pvliesdonk/image-generation-mcp/commit/cdf9c60720d0167bfc040d6fe07986149982acec))

- **ci**: Replace Codecov cloud dependency with local diff-cover for patch coverage gate (#102)
  ([#102](https://github.com/pvliesdonk/image-generation-mcp/pull/102),
  [`2f9030f`](https://github.com/pvliesdonk/image-generation-mcp/commit/2f9030ffdc76ab8a183b8b00efd1de31b9ddb865))

### Chores

- Update server.json to v1.1.0 [skip ci]
  ([`5611d24`](https://github.com/pvliesdonk/image-generation-mcp/commit/5611d24787c4d2c86d255454b95e66fe341875fd))

### Features

- Elicitation confirmation for paid image providers (#88)
  ([#88](https://github.com/pvliesdonk/image-generation-mcp/pull/88),
  [`d4580fb`](https://github.com/pvliesdonk/image-generation-mcp/commit/d4580fba2d0e4371d30b2f91322df7398ed3e76d))

- Show model name and auto-generate download link in show_image (#87)
  ([#87](https://github.com/pvliesdonk/image-generation-mcp/pull/87),
  [`ac66c4b`](https://github.com/pvliesdonk/image-generation-mcp/commit/ac66c4bfe18d91abd2e05dd60ba2eaa1ecd94bc2))

- Support RemoteAuthProvider as default OIDC mode (#99) (#100)
  ([#100](https://github.com/pvliesdonk/image-generation-mcp/pull/100),
  [`cb1d669`](https://github.com/pvliesdonk/image-generation-mcp/commit/cb1d6694e63eeff976e440ef0586a51ea9a6dbb3))

### Refactoring

- Derive ProviderCapabilities.supports_* as properties from models (#53) (#91)
  ([#91](https://github.com/pvliesdonk/image-generation-mcp/pull/91),
  [`eb9eb4c`](https://github.com/pvliesdonk/image-generation-mcp/commit/eb9eb4c013ea09243a8b614509cf84a91e9b2142))

- Move config tests from test_transform_cache.py to test_config.py (#89) (#90)
  ([#90](https://github.com/pvliesdonk/image-generation-mcp/pull/90),
  [`41020ba`](https://github.com/pvliesdonk/image-generation-mcp/commit/41020ba95d6f2ad79816d34358a7660093fec107))

- Parallelize A1111 discovery API calls with asyncio.gather (#52) (#92)
  ([#92](https://github.com/pvliesdonk/image-generation-mcp/pull/92),
  [`72f3449`](https://github.com/pvliesdonk/image-generation-mcp/commit/72f34497cb99ef9637a4c82fe2662f6bc9b8c22f))

### Testing

- Add MCP-level integration tests for image resources and generate_image tool (#22) (#93)
  ([#93](https://github.com/pvliesdonk/image-generation-mcp/pull/93),
  [`ffc5e71`](https://github.com/pvliesdonk/image-generation-mcp/commit/ffc5e71600141ab3b1e025271ab7795fdbe427bd))

- Raise test coverage to 80% with meaningful tests (#36) (#94)
  ([#94](https://github.com/pvliesdonk/image-generation-mcp/pull/94),
  [`e866604`](https://github.com/pvliesdonk/image-generation-mcp/commit/e86660463ff9f8e871b908bdfe3bfa8ee02b656d))


## 1.1.0 (2026-03-21)

### Bug Fixes

- Add localStorage persistence to image viewer for restore (#81)
  ([#81](https://github.com/pvliesdonk/image-generation-mcp/pull/81),
  [`cc8301a`](https://github.com/pvliesdonk/image-generation-mcp/commit/cc8301a67073fa1018d9f85869dd2f486fe99e9e))

- Cap show_image thumbnail and document client compatibility (#83)
  ([#83](https://github.com/pvliesdonk/image-generation-mcp/pull/83),
  [`6782fbf`](https://github.com/pvliesdonk/image-generation-mcp/commit/6782fbf015540727bda373993eeeed298ec3f43a))

- Disable FastMCP consent page — Authelia handles consent
  ([`6b1afc0`](https://github.com/pvliesdonk/image-generation-mcp/commit/6b1afc0ce5e05c0ec99a81eb92d45a0147cfc94a))

- **a1111**: Split sampler and scheduler for A1111 >=1.6 (#63)
  ([#63](https://github.com/pvliesdonk/image-generation-mcp/pull/63),
  [`a223623`](https://github.com/pvliesdonk/image-generation-mcp/commit/a223623bb40dd51677605010b40a03a4e5a72df0))

- **auth**: Pass required_scopes=[] to MultiAuth (#38) (#41)
  ([#41](https://github.com/pvliesdonk/image-generation-mcp/pull/41),
  [`13487df`](https://github.com/pvliesdonk/image-generation-mcp/commit/13487df7b656f52ba1169bd3df736871647e07b0))

### Chores

- Update server.json to v1.0.0 [skip ci]
  ([`39677ee`](https://github.com/pvliesdonk/image-generation-mcp/commit/39677ee2ae2e25329fdcfe54ccdc66beb85597ab))

### Documentation

- ADR-0007 provider capability model design (#45)
  ([#45](https://github.com/pvliesdonk/image-generation-mcp/pull/45),
  [`6762165`](https://github.com/pvliesdonk/image-generation-mcp/commit/67621659c477941f793550997a0c06800da9e6ac))

- Update design docs and user-facing docs for Milestone 3 (#51)
  ([#51](https://github.com/pvliesdonk/image-generation-mcp/pull/51),
  [`abce3b2`](https://github.com/pvliesdonk/image-generation-mcp/commit/abce3b2e16a892706f0a06911770982db4a2703d))

- **deployment**: Systemd deployment guide (#40) (#44)
  ([#44](https://github.com/pvliesdonk/image-generation-mcp/pull/44),
  [`9c43745`](https://github.com/pvliesdonk/image-generation-mcp/commit/9c43745f5b7bc9ca294aced2c85a4e79416e79d0))

### Features

- Add background transparency parameter to generate_image (#49)
  ([#49](https://github.com/pvliesdonk/image-generation-mcp/pull/49),
  [`226648c`](https://github.com/pvliesdonk/image-generation-mcp/commit/226648c15845dc9b5488d484d4d11bf486fae84c))

- Create_download_link tool with one-time HTTP download URLs (#73)
  ([#73](https://github.com/pvliesdonk/image-generation-mcp/pull/73),
  [`0ed11e8`](https://github.com/pvliesdonk/image-generation-mcp/commit/0ed11e886ad811f2f22e989edef512d3ecd262c3))

- In-memory LRU cache for image resource transforms (#74)
  ([#74](https://github.com/pvliesdonk/image-generation-mcp/pull/74),
  [`aa52dd1`](https://github.com/pvliesdonk/image-generation-mcp/commit/aa52dd1defd935c39e2df418a39f6fe23ffc2c1a))

- Info://prompt-guide resource with per-provider prompt writing guidance (#75)
  ([#75](https://github.com/pvliesdonk/image-generation-mcp/pull/75),
  [`5f3543a`](https://github.com/pvliesdonk/image-generation-mcp/commit/5f3543af424e9817ed4321ac114a453fca2c20af))

- Per-call model selection on generate_image (#71)
  ([#71](https://github.com/pvliesdonk/image-generation-mcp/pull/71),
  [`7293e66`](https://github.com/pvliesdonk/image-generation-mcp/commit/7293e66c4b026d7d87fcc1694f28f37dbfb768c9))

- ProviderCapabilities dataclasses + protocol extension + placeholder impl (#54)
  ([#54](https://github.com/pvliesdonk/image-generation-mcp/pull/54),
  [`897d965`](https://github.com/pvliesdonk/image-generation-mcp/commit/897d9652ddf518c17d3af1589f09358d7fd888a6))

- Split generate_image / show_image into separate tools (#77)
  ([#77](https://github.com/pvliesdonk/image-generation-mcp/pull/77),
  [`9bb178d`](https://github.com/pvliesdonk/image-generation-mcp/commit/9bb178d8d7bff9c4d080d3fefc1e95edc495c6d5))

- Surface provider capabilities in MCP tools, resources, and selector (#50)
  ([#50](https://github.com/pvliesdonk/image-generation-mcp/pull/50),
  [`2b07e5f`](https://github.com/pvliesdonk/image-generation-mcp/commit/2b07e5fab8334b267362ee510e3ccb3fb797e7a4))

- **a1111**: Checkpoint discovery + architecture-aware capabilities (#48)
  ([#48](https://github.com/pvliesdonk/image-generation-mcp/pull/48),
  [`17bb73e`](https://github.com/pvliesdonk/image-generation-mcp/commit/17bb73e5a5ac15fe583eacc28265afeeca97d0f8))

- **apps**: MCP Apps image viewer for generate_image results (#64) (#65)
  ([#65](https://github.com/pvliesdonk/image-generation-mcp/pull/65),
  [`627e3e2`](https://github.com/pvliesdonk/image-generation-mcp/commit/627e3e275f7df9279601d0c6b291e09f7fab246d))

- **openai**: Capability discovery via models.list() (#47)
  ([#47](https://github.com/pvliesdonk/image-generation-mcp/pull/47),
  [`2bc67cd`](https://github.com/pvliesdonk/image-generation-mcp/commit/2bc67cd36bb1a50872d1df209d3f3eaf41a05b9a))

- **packaging**: Linux .deb/.rpm packages with systemd service (#39) (#43)
  ([#43](https://github.com/pvliesdonk/image-generation-mcp/pull/43),
  [`f926a74`](https://github.com/pvliesdonk/image-generation-mcp/commit/f926a74052d57314e3a9083f19cedee0a564ee39))

- **registry**: MCP Registry submission readiness (#37) (#42)
  ([#42](https://github.com/pvliesdonk/image-generation-mcp/pull/42),
  [`345499e`](https://github.com/pvliesdonk/image-generation-mcp/commit/345499ec2fb055e586f218afa152bbcf18dd076f))

- **tools**: Add get_image and list_images tools for tool-only MCP clients (#61)
  ([#61](https://github.com/pvliesdonk/image-generation-mcp/pull/61),
  [`8496e8e`](https://github.com/pvliesdonk/image-generation-mcp/commit/8496e8e0ffed4bffcf3c214f18fe4d3177a3be71))

### Refactoring

- Consolidate onto FastMCP logging stack (#80) (#82)
  ([#82](https://github.com/pvliesdonk/image-generation-mcp/pull/82),
  [`f82799c`](https://github.com/pvliesdonk/image-generation-mcp/commit/f82799c03f36329c7080a7daaf949eee3980cafa))


## 1.0.0 (2026-03-19)

- Initial Release
