<!-- SINH TỰ ĐỘNG từ contract/methods.json — ĐỪNG SỬA TAY. -->
# Method map

Generated from `contract/methods.json` v1.0.0 by `tools/generate.py`.

Python uses `snake_case`, JavaScript uses `camelCase`; the order and the semantics are
identical, because both sides are generated from the same table.

| Python | JavaScript | HTTP | Retried on failure |
|---|---|---|---|
| `signup(username, password)` | `signup(username, password)` | `POST /api/signup` | no, it may have arrived |
| `login(username, password)` | `login(username, password)` | `POST /api/login` | no, it may have arrived |
| `me()` | `me()` | `GET /api/me` | yes, it is a read |
| `logout()` | `logout()` | `POST /api/logout` | no, it may have arrived |
| `logout_all()` | `logoutAll()` | `POST /api/logout-all` | no, it may have arrived |
| `health()` | `health()` | `GET /api/health` | yes, it is a read |
| `describe()` | `describe()` | `GET /.well-known/orilife.json` | yes, it is a read |
| `endpoints()` | `endpoints()` | `GET /api` | yes, it is a read |
| `species_catalog()` | `speciesCatalog()` | `GET /api/species/catalog` | yes, it is a read |
| `resolve(code)` | `resolve(code)` | `GET /api/resolve/{code}` | yes, it is a read |
| `tree_by_code(code)` | `treeByCode(code)` | `GET /api/tree_by_code/{code}` | yes, it is a read |
| `lookup_fruit(image)` | `lookupFruit(image)` | `POST /api/fruit/lookup` | no, it may have arrived |
| `identify_auto(images, *, lat, lon, species, farm_id)` | `identifyAuto(images, { lat, lon, species, farmId })` | `POST /api/identify/auto` | no, it may have arrived |
| `identify_tree(images, *, lat, lon, last_tree)` | `identifyTree(images, { lat, lon, lastTree })` | `POST /api/identify` | no, it may have arrived |
| `identify_tree_video(video, *, lat, lon)` | `identifyTreeVideo(video, { lat, lon })` | `POST /api/identify/video` | no, it may have arrived |
| `identify_fruit(image, *, tree_id)` | `identifyFruit(image, { treeId })` | `POST /api/fruit/identify` | no, it may have arrived |
| `identify_animal(image, *, species, farm_id)` | `identifyAnimal(image, { species, farmId })` | `POST /api/animal/identify` | no, it may have arrived |
| `identify_kind(image)` | `identifyKind(image)` | `POST /api/kind` | no, it may have arrived |
| `scan_animal(image, *, farm_id, species)` | `scanAnimal(image, { farmId, species })` | `POST /api/animal/scan` | no, it may have arrived |
| `enroll_tree(images, *, name, lat, lon, farm_id, species)` | `enrollTree(images, { name, lat, lon, farmId, species })` | `POST /api/enroll` | no, it may have arrived |
| `verify_add(tree_id, images)` | `verifyAdd(treeId, images)` | `POST /api/verify_add` | no, it may have arrived |
| `list_trees(*, farm_id)` | `listTrees({ farmId })` | `GET /api/trees` | yes, it is a read |
| `enroll_fruit(images, *, tree_id, name, bbox)` | `enrollFruit(images, { treeId, name, bbox })` | `POST /api/fruit/enroll` | no, it may have arrived |
| `add_fruit_view(fruit_id, images)` | `addFruitView(fruitId, images)` | `POST /api/fruit/add_view` | no, it may have arrived |
| `enroll_animal(images, *, species, farm_id, name, owner_did)` | `enrollAnimal(images, { species, farmId, name, ownerDid })` | `POST /api/animal/enroll` | no, it may have arrived |
| `list_animals(*, farm_id, species, limit, offset)` | `listAnimals({ farmId, species, limit, offset })` | `GET /api/animal/list` | yes, it is a read |
| `create_farm(name, *, lat, lon)` | `createFarm(name, { lat, lon })` | `POST /api/farm` | no, it may have arrived |
| `list_farms()` | `listFarms()` | `GET /api/farms` | yes, it is a read |
| `get_farm(farm_id)` | `getFarm(farmId)` | `GET /api/farm/{farm_id}` | yes, it is a read |
| `update_farm(farm_id, *, **fields)` | `updateFarm(farmId, fields)` | `POST /api/farm/{farm_id}/update` | no, it may have arrived |
| `delete_farm(farm_id)` | `deleteFarm(farmId)` | `DELETE /api/farm/{farm_id}` | no, it may have arrived |
| `submit_verdict(query_id, verdict, *, correct_tree_id)` | `submitVerdict(queryId, verdict, { correctTreeId })` | `POST /api/identify_verdict` | no, it may have arrived |
| `submit_fruit_verdict(query_id, verdict, *, correct_fruit_id)` | `submitFruitVerdict(queryId, verdict, { correctFruitId })` | `POST /api/fruit/identify_verdict` | no, it may have arrived |
| `submit_animal_verdict(query_id, verdict, *, correct_did)` | `submitAnimalVerdict(queryId, verdict, { correctDid })` | `POST /api/animal/identify_verdict` | no, it may have arrived |
| `capture_plan(entity_type, entity_id)` | `capturePlan(entityType, entityId)` | `GET /api/capture/plan` | yes, it is a read |
| `provenance(tree_id)` | `provenance(treeId)` | `GET /api/provenance/{tree_id}` | yes, it is a read |
| `timeline(entity_type, entity_id)` | `timeline(entityType, entityId)` | `GET /api/{entity_type}/{entity_id}/timeline` | yes, it is a read |
| `proof(entity_type, entity_id, event_id)` | `proof(entityType, entityId, eventId)` | `GET /api/{entity_type}/{entity_id}/proof/{event_id}` | yes, it is a read |
| `add_event(entity_type, entity_id, kind, data)` | `addEvent(entityType, entityId, kind, data)` | `POST /api/{entity_type}/{entity_id}/event` | no, it may have arrived |
| `anchor_event(entity_type, entity_id, event_id)` | `anchorEvent(entityType, entityId, eventId)` | `POST /api/{entity_type}/{entity_id}/event/{event_id}/anchor` | no, it may have arrived |

## Not generated

| Method | Why it is written by hand |
|---|---|
| `supports()` / `supports()` | It is not one HTTP call: it reads GET /api once, caches the answer, and turns 404 into false. |

Two places where the SDK argument name differs from the HTTP field name, because the
HTTP names are abbreviations kept for backward compatibility:

| SDK argument | HTTP field |
|---|---|
| `correct_tree_id` | `correct_tid` |
| `entity_type` / `entity_id` in `capture_plan` | `target_type` / `target_id` |
