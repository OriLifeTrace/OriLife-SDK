<!-- GENERATED from contract/methods.json — DO NOT EDIT BY HAND. -->
# Method map

Generated from `contract/methods.json` v1.1.0 by `tools/generate.py`.

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
| `did_challenge()` | `didChallenge()` | `GET /api/auth/did/challenge` | yes, it is a read |
| `login_with_did(did, challenge, signature, *, pubkey_hex)` | `loginWithDid(did, challenge, signature, { pubkeyHex })` | `POST /api/auth/did/verify` | no, it may have arrived |
| `account_data()` | `accountData()` | `GET /api/account/data` | yes, it is a read |
| `delete_account(confirm)` | `deleteAccount(confirm)` | `POST /api/account/delete` | no, it may have arrived |
| `resolve_account(username)` | `resolveAccount(username)` | `GET /api/account/resolve` | yes, it is a read |
| `create_grant(grantee, scope_type, scope_id, perms, *, ttl_days, client_event_id)` | `createGrant(grantee, scopeType, scopeId, perms, { ttlDays, clientEventId })` | `POST /api/grant` | no, it may have arrived |
| `list_grants()` | `listGrants()` | `GET /api/grants` | yes, it is a read |
| `revoke_grant(grant_id)` | `revokeGrant(grantId)` | `DELETE /api/grant/{grant_id}` | no, it may have arrived |
| `match_care_product(*, text, scope, images)` | `matchCareProduct({ text, scope, images })` | `POST /api/care/match` | no, it may have arrived |
| `log_care(target_type, target_id, product_id, *, applied_at, dose, purpose, farm_id, recognition_method, client_event_id, images)` | `logCare(targetType, targetId, productId, { appliedAt, dose, purpose, farmId, recognitionMethod, clientEventId, images })` | `POST /api/care/log` | no, it may have arrived |
| `list_care_events(target_type, target_id)` | `listCareEvents(targetType, targetId)` | `GET /api/care/events` | yes, it is a read |
| `list_care_products(*, scope, category)` | `listCareProducts({ scope, category })` | `GET /api/care/products` | yes, it is a read |
| `withdrawal_status(target_type, target_id)` | `withdrawalStatus(targetType, targetId)` | `GET /api/care/withdrawal` | yes, it is a read |
| `list_banned_substances(*, q, scope, severity)` | `listBannedSubstances({ q, scope, severity })` | `GET /api/care/banned` | yes, it is a read |
| `delete_care_event(care_event_id)` | `deleteCareEvent(careEventId)` | `POST /api/care/delete` | no, it may have arrived |
| `interpret_residue(market, measurements, *, phi_gate_open, cd_soil, soil_ph)` | `interpretResidue(market, measurements, { phiGateOpen, cdSoil, soilPh })` | `POST /api/residue/interpret` | no, it may have arrived |
| `rename_tree(tree_id, name)` | `renameTree(treeId, name)` | `POST /api/rename` | no, it may have arrived |
| `delete_tree(tree_id)` | `deleteTree(treeId)` | `POST /api/delete` | no, it may have arrived |
| `update_tree_location(tree_id, lat, lon)` | `updateTreeLocation(treeId, lat, lon)` | `POST /api/update_location` | no, it may have arrived |
| `set_tree_visibility(tree_id, visibility, *, expose_location, public_card)` | `setTreeVisibility(treeId, visibility, { exposeLocation, publicCard })` | `POST /api/tree/set_visibility` | no, it may have arrived |
| `set_tree_farm(tree_id, *, farm_id)` | `setTreeFarm(treeId, { farmId })` | `POST /api/tree/set_farm` | no, it may have arrived |
| `set_tree_position(tree_id, x, z)` | `setTreePosition(treeId, x, z)` | `POST /api/tree/set_position` | no, it may have arrived |
| `clear_tree_position(tree_id)` | `clearTreePosition(treeId)` | `POST /api/tree/set_position` | no, it may have arrived |
| `set_tree_species(tree_id, *, species)` | `setTreeSpecies(treeId, { species })` | `POST /api/tree/set_species` | no, it may have arrived |
| `add_tree_marker(tree_id, label, side)` | `addTreeMarker(treeId, label, side)` | `POST /api/tree/marker` | no, it may have arrived |
| `tree_views(tree_id)` | `treeViews(treeId)` | `GET /api/tree_views` | yes, it is a read |
| `remove_tree_views(tree_id, indices)` | `removeTreeViews(treeId, indices)` | `POST /api/remove_views` | no, it may have arrived |
| `tree_drift(tree_id)` | `treeDrift(treeId)` | `GET /api/tree_drift/{tree_id}` | yes, it is a read |
| `capture_guidance(tree_id)` | `captureGuidance(treeId)` | `GET /api/capture_guidance/{tree_id}` | yes, it is a read |
| `tree_growth(tree_id)` | `treeGrowth(treeId)` | `GET /api/tree/{tree_id}/growth` | yes, it is a read |
| `tree_model3d(tree_id, *, max_points, max_fruits, max_segments, colors, format)` | `treeModel3d(treeId, { maxPoints, maxFruits, maxSegments, colors, format })` | `GET /api/tree/{tree_id}/model3d` | yes, it is a read |
| `public_tree_model3d(code, *, max_points, max_fruits, max_segments, colors, format)` | `publicTreeModel3d(code, { maxPoints, maxFruits, maxSegments, colors, format })` | `GET /api/tree_by_code/{code}/model3d` | yes, it is a read |
| `get_tree_profile(tree_id)` | `getTreeProfile(treeId)` | `GET /api/tree/{tree_id}/profile` | yes, it is a read |
| `update_tree_profile(tree_id, profile)` | `updateTreeProfile(treeId, profile)` | `POST /api/tree/{tree_id}/profile` | no, it may have arrived |
| `add_tree_video(tree_id, video, *, lat, lon, note)` | `addTreeVideo(treeId, video, { lat, lon, note })` | `POST /api/tree/{tree_id}/video` | no, it may have arrived |
| `add_fruit_video(tree_id, video, *, lat, lon, note, fruit_id, client_event_id)` | `addFruitVideo(treeId, video, { lat, lon, note, fruitId, clientEventId })` | `POST /api/tree/{tree_id}/fruit_video` | no, it may have arrived |
| `farm_map(farm_id)` | `farmMap(farmId)` | `GET /api/farm/{farm_id}/map` | yes, it is a read |
| `farm_layout()` | `farmLayout()` | `GET /api/farm/layout` | yes, it is a read |
| `tree_layout(tree_id)` | `treeLayout(treeId)` | `GET /api/tree/{tree_id}/layout` | yes, it is a read |
| `detect_fruit(image, *, tree_id)` | `detectFruit(image, { treeId })` | `POST /api/fruit/detect` | no, it may have arrived |
| `fruit_candidates(image, *, tree_id, bbox)` | `fruitCandidates(image, { treeId, bbox })` | `POST /api/fruit/candidates` | no, it may have arrived |
| `list_fruits(*, tree_id)` | `listFruits({ treeId })` | `GET /api/fruit/list` | yes, it is a read |
| `get_fruit(fruit_id)` | `getFruit(fruitId)` | `GET /api/fruit/{fruit_id}` | yes, it is a read |
| `fruit_views(fruit_id)` | `fruitViews(fruitId)` | `GET /api/fruit/{fruit_id}/views` | yes, it is a read |
| `set_fruit_status(fruit_id, status)` | `setFruitStatus(fruitId, status)` | `PATCH /api/fruit/{fruit_id}/status` | no, it may have arrived |
| `delete_fruit(fruit_id)` | `deleteFruit(fruitId)` | `DELETE /api/fruit/{fruit_id}` | no, it may have arrived |
| `fruit_model3d(fruit_id)` | `fruitModel3d(fruitId)` | `GET /api/fruit/{fruit_id}/model3d` | yes, it is a read |
| `rename_animal(animal_did, name)` | `renameAnimal(animalDid, name)` | `POST /api/animal/rename` | no, it may have arrived |
| `verify_animal(animal_did, image)` | `verifyAnimal(animalDid, image)` | `POST /api/animal/verify` | no, it may have arrived |
| `get_animal(animal_did)` | `getAnimal(animalDid)` | `GET /api/animal/{animal_did}` | yes, it is a read |
| `delete_animal(animal_did)` | `deleteAnimal(animalDid)` | `DELETE /api/animal/{animal_did}` | no, it may have arrived |
| `animal_model3d(animal_did)` | `animalModel3d(animalDid)` | `GET /api/animal/{animal_did}/model3d` | yes, it is a read |
| `detect_animal_species(farm_id, *, image)` | `detectAnimalSpecies(farmId, { image })` | `POST /api/animal/detect` | no, it may have arrived |
| `animal_drift_report(farm_id)` | `animalDriftReport(farmId)` | `GET /api/animal/drift/report` | yes, it is a read |
| `scan_species(images)` | `scanSpecies(images)` | `POST /api/scan` | no, it may have arrived |
| `confirm_species(scan_token, species)` | `confirmSpecies(scanToken, species)` | `POST /api/scan/confirm` | no, it may have arrived |
| `record_population_count(farm_id, zone_id, zone_name, count, *, method, device_id)` | `recordPopulationCount(farmId, zoneId, zoneName, count, { method, deviceId })` | `POST /api/population/count` | no, it may have arrived |
| `population_dashboard(farm_id)` | `populationDashboard(farmId)` | `GET /api/population/farm/{farm_id}` | yes, it is a read |
| `population_alerts(farm_id)` | `populationAlerts(farmId)` | `GET /api/population/alerts/{farm_id}` | yes, it is a read |
| `entity_did(entity_type, entity_id)` | `entityDid(entityType, entityId)` | `GET /api/{entity_type}/{entity_id}/did` | yes, it is a read |
| `request_entity_did(entity_type, entity_id)` | `requestEntityDid(entityType, entityId)` | `POST /api/{entity_type}/{entity_id}/did/request` | no, it may have arrived |
| `submit_entity_did(entity_type, entity_id, owner_signature)` | `submitEntityDid(entityType, entityId, ownerSignature)` | `POST /api/{entity_type}/{entity_id}/did/submit` | no, it may have arrived |
| `magic_tasks()` | `magicTasks()` | `GET /api/magic/tasks` | yes, it is a read |
| `send_feedback(note, *, context)` | `sendFeedback(note, { context })` | `POST /api/feedback` | no, it may have arrived |

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
