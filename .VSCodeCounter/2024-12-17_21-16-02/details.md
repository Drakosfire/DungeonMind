# Details

Date : 2024-12-17 21:16:02

Directory /media/drakosfire/Shared1/DungeonMind/DungeonMindServer

Total : 147 files,  1920155 codes, 1158 comments, 4643 blanks, all 1925956 lines

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [.dockerignore](/.dockerignore) | Ignore | 28 | 4 | 4 | 36 |
| [Dockerfile](/Dockerfile) | Docker | 14 | 12 | 11 | 37 |
| [README.md](/README.md) | Markdown | 30 | 0 | 17 | 47 |
| [TODO.md](/TODO.md) | Markdown | 6 | 0 | 2 | 8 |
| [__init__.py](/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [app.py](/app.py) | Python | 105 | 16 | 30 | 151 |
| [cardgenerator/__init__.py](/cardgenerator/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [cardgenerator/cardgenerator_helper.py](/cardgenerator/cardgenerator_helper.py) | Python | 0 | 0 | 1 | 1 |
| [cardgenerator/prompts.py](/cardgenerator/prompts.py) | Python | 269 | 0 | 44 | 313 |
| [cloudflare/__init__.py](/cloudflare/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [cloudflare/handle_images.py](/cloudflare/handle_images.py) | Python | 42 | 4 | 11 | 57 |
| [cloudflareR2/__init__.py](/cloudflareR2/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [cloudflareR2/cloudflareR2_utils.py](/cloudflareR2/cloudflareR2_utils.py) | Python | 32 | 23 | 12 | 67 |
| [cloudflareR2/r2_config.py](/cloudflareR2/r2_config.py) | Python | 22 | 15 | 7 | 44 |
| [compressimages.sh](/compressimages.sh) | Shell Script | 22 | 7 | 7 | 36 |
| [dependencies.py](/dependencies.py) | Python | 12 | 0 | 2 | 14 |
| [deploy.sh](/deploy.sh) | Shell Script | 22 | 10 | 12 | 44 |
| [deploylocal.sh](/deploylocal.sh) | Shell Script | 20 | 9 | 11 | 40 |
| [extractimages.sh](/extractimages.sh) | Shell Script | 25 | 8 | 10 | 43 |
| [firestore/__init__.py](/firestore/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [firestore/firebase_config.py](/firestore/firebase_config.py) | Python | 5 | 2 | 3 | 10 |
| [firestore/firestore_utils.py](/firestore/firestore_utils.py) | Python | 19 | 0 | 6 | 25 |
| [pixel_art_landing_page_plan.md](/pixel_art_landing_page_plan.md) | Markdown | 92 | 0 | 28 | 120 |
| [poetry.lock](/poetry.lock) | toml | 2,849 | 0 | 220 | 3,069 |
| [pytest.ini](/pytest.ini) | Ini | 4 | 0 | 1 | 5 |
| [routers/__init__.py](/routers/__init__.py) | Python | 13 | 0 | 1 | 14 |
| [routers/auth_router.py](/routers/auth_router.py) | Python | 76 | 21 | 23 | 120 |
| [routers/cardgenerator_router.py](/routers/cardgenerator_router.py) | Python | 60 | 5 | 13 | 78 |
| [routers/debug_router.py](/routers/debug_router.py) | Python | 10 | 1 | 4 | 15 |
| [routers/ruleslawyer_router.py](/routers/ruleslawyer_router.py) | Python | 78 | 4 | 17 | 99 |
| [routers/session_router.py](/routers/session_router.py) | Python | 100 | 0 | 8 | 108 |
| [routers/store_router.py](/routers/store_router.py) | Python | 113 | 26 | 24 | 163 |
| [ruleslawyer/DnD_PHB_55.json](/ruleslawyer/DnD_PHB_55.json) | JSON | 745,947 | 0 | 0 | 745,947 |
| [ruleslawyer/PathGM.json](/ruleslawyer/PathGM.json) | JSON | 496,366 | 0 | 0 | 496,366 |
| [ruleslawyer/__init__.py](/ruleslawyer/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [ruleslawyer/ruleslawyer_helper.py](/ruleslawyer/ruleslawyer_helper.py) | Python | 110 | 18 | 30 | 158 |
| [ruleslawyer/swcr.json](/ruleslawyer/swcr.json) | JSON | 290,032 | 0 | 0 | 290,032 |
| [ruleslawyer/swon.json](/ruleslawyer/swon.json) | JSON | 360,352 | 0 | 0 | 360,352 |
| [session_management.py](/session_management.py) | Python | 71 | 2 | 13 | 86 |
| [session_router.py](/session_router.py) | Python | 100 | 0 | 8 | 108 |
| [static/build/asset-manifest.json](/static/build/asset-manifest.json) | JSON | 15 | 0 | 0 | 15 |
| [static/build/index.html](/static/build/index.html) | HTML | 1 | 0 | 0 | 1 |
| [static/build/manifest.json](/static/build/manifest.json) | JSON | 26 | 0 | 0 | 26 |
| [static/build/static/css/main.aa4e78f1.css](/static/build/static/css/main.aa4e78f1.css) | CSS | 1 | 1 | 0 | 2 |
| [static/build/static/js/453.20a124db.chunk.js](/static/build/static/js/453.20a124db.chunk.js) | JavaScript | 1 | 1 | 0 | 2 |
| [static/build/static/js/main.b894e31a.js](/static/build/static/js/main.b894e31a.js) | JavaScript | 1 | 2 | 0 | 3 |
| [static/css/main.bc78b7de.css](/static/css/main.bc78b7de.css) | CSS | 159 | 1 | 28 | 188 |
| [static/css/style.css](/static/css/style.css) | CSS | 154 | 0 | 28 | 182 |
| [static/js/453.0530a65a.chunk.js](/static/js/453.0530a65a.chunk.js) | JavaScript | 1 | 1 | 0 | 2 |
| [static/js/main.3fc47861.js](/static/js/main.3fc47861.js) | JavaScript | 1 | 2 | 0 | 3 |
| [static/root_store/Enchanted_Roots_Gear_Emporium/Enchanted_Roots_Gear_Emporium.json](/static/root_store/Enchanted_Roots_Gear_Emporium/Enchanted_Roots_Gear_Emporium.json) | JSON | 236 | 0 | 0 | 236 |
| [static/storegenerator/css/5ePHBstyle.css](/static/storegenerator/css/5ePHBstyle.css) | CSS | 1,248 | 0 | 232 | 1,480 |
| [static/storegenerator/css/all.css](/static/storegenerator/css/all.css) | CSS | 4,628 | 4 | 1,509 | 6,141 |
| [static/storegenerator/css/bundle.css](/static/storegenerator/css/bundle.css) | CSS | 4,277 | 0 | 872 | 5,149 |
| [static/storegenerator/css/css.css](/static/storegenerator/css/css.css) | CSS | 256 | 32 | 1 | 289 |
| [static/storegenerator/css/phb.standalone.css](/static/storegenerator/css/phb.standalone.css) | CSS | 645 | 0 | 100 | 745 |
| [static/storegenerator/css/storeUI.css](/static/storegenerator/css/storeUI.css) | CSS | 654 | 97 | 90 | 841 |
| [static/storegenerator/css/style.css](/static/storegenerator/css/style.css) | CSS | 606 | 3 | 139 | 748 |
| [static/storegenerator/scripts/blockBuilder.js](/static/storegenerator/scripts/blockBuilder.js) | JavaScript | 272 | 28 | 40 | 340 |
| [static/storegenerator/scripts/blockHandler.js](/static/storegenerator/scripts/blockHandler.js) | JavaScript | 128 | 30 | 34 | 192 |
| [static/storegenerator/scripts/config.js](/static/storegenerator/scripts/config.js) | JavaScript | 14 | 9 | 2 | 25 |
| [static/storegenerator/scripts/domInit.js](/static/storegenerator/scripts/domInit.js) | JavaScript | 28 | 5 | 8 | 41 |
| [static/storegenerator/scripts/dragDropHandler.js](/static/storegenerator/scripts/dragDropHandler.js) | JavaScript | 116 | 102 | 35 | 253 |
| [static/storegenerator/scripts/eventHandlers.js](/static/storegenerator/scripts/eventHandlers.js) | JavaScript | 182 | 55 | 49 | 286 |
| [static/storegenerator/scripts/handleTextareas.js](/static/storegenerator/scripts/handleTextareas.js) | JavaScript | 74 | 25 | 19 | 118 |
| [static/storegenerator/scripts/jsonToBlocks.js](/static/storegenerator/scripts/jsonToBlocks.js) | JavaScript | 194 | 19 | 20 | 233 |
| [static/storegenerator/scripts/loadingImage.js](/static/storegenerator/scripts/loadingImage.js) | JavaScript | 45 | 6 | 11 | 62 |
| [static/storegenerator/scripts/main.js](/static/storegenerator/scripts/main.js) | JavaScript | 51 | 7 | 9 | 67 |
| [static/storegenerator/scripts/pageHandler.js](/static/storegenerator/scripts/pageHandler.js) | JavaScript | 133 | 13 | 31 | 177 |
| [static/storegenerator/scripts/saveLoadHandler.js](/static/storegenerator/scripts/saveLoadHandler.js) | JavaScript | 177 | 27 | 29 | 233 |
| [static/storegenerator/scripts/state.js](/static/storegenerator/scripts/state.js) | JavaScript | 16 | 2 | 3 | 21 |
| [static/storegenerator/scripts/trashHandler.js](/static/storegenerator/scripts/trashHandler.js) | JavaScript | 57 | 10 | 9 | 76 |
| [static/storegenerator/scripts/utils.js](/static/storegenerator/scripts/utils.js) | JavaScript | 144 | 13 | 22 | 179 |
| [static/storegenerator/themes/Legacy/5ePHB/settings.json](/static/storegenerator/themes/Legacy/5ePHB/settings.json) | JSON with Comments | 5 | 0 | 1 | 6 |
| [static/storegenerator/themes/Legacy/5ePHB/snippets.js](/static/storegenerator/themes/Legacy/5ePHB/snippets.js) | JavaScript | 298 | 5 | 25 | 328 |
| [static/storegenerator/themes/Legacy/5ePHB/snippets/classfeature.gen.js](/static/storegenerator/themes/Legacy/5ePHB/snippets/classfeature.gen.js) | JavaScript | 45 | 0 | 8 | 53 |
| [static/storegenerator/themes/Legacy/5ePHB/snippets/classtable.gen.js](/static/storegenerator/themes/Legacy/5ePHB/snippets/classtable.gen.js) | JavaScript | 99 | 0 | 16 | 115 |
| [static/storegenerator/themes/Legacy/5ePHB/snippets/coverpage.gen.js](/static/storegenerator/themes/Legacy/5ePHB/snippets/coverpage.gen.js) | JavaScript | 109 | 0 | 8 | 117 |
| [static/storegenerator/themes/Legacy/5ePHB/snippets/fullclass.gen.js](/static/storegenerator/themes/Legacy/5ePHB/snippets/fullclass.gen.js) | JavaScript | 31 | 0 | 12 | 43 |
| [static/storegenerator/themes/Legacy/5ePHB/snippets/magic.gen.js](/static/storegenerator/themes/Legacy/5ePHB/snippets/magic.gen.js) | JavaScript | 82 | 0 | 10 | 92 |
| [static/storegenerator/themes/Legacy/5ePHB/snippets/monsterblock.gen.js](/static/storegenerator/themes/Legacy/5ePHB/snippets/monsterblock.gen.js) | JavaScript | 188 | 0 | 13 | 201 |
| [static/storegenerator/themes/Legacy/5ePHB/snippets/tableOfContents.gen.js](/static/storegenerator/themes/Legacy/5ePHB/snippets/tableOfContents.gen.js) | JavaScript | 68 | 0 | 4 | 72 |
| [static/storegenerator/themes/Legacy/5ePHB/style.less](/static/storegenerator/themes/Legacy/5ePHB/style.less) | Less | 448 | 51 | 3 | 502 |
| [static/storegenerator/themes/V3/5eDMG/settings.json](/static/storegenerator/themes/V3/5eDMG/settings.json) | JSON with Comments | 6 | 0 | 1 | 7 |
| [static/storegenerator/themes/V3/5eDMG/snippets.js](/static/storegenerator/themes/V3/5eDMG/snippets.js) | JavaScript | 2 | 1 | 2 | 5 |
| [static/storegenerator/themes/V3/5eDMG/style.less](/static/storegenerator/themes/V3/5eDMG/style.less) | Less | 31 | 3 | 10 | 44 |
| [static/storegenerator/themes/V3/5ePHB/settings.json](/static/storegenerator/themes/V3/5ePHB/settings.json) | JSON with Comments | 6 | 0 | 1 | 7 |
| [static/storegenerator/themes/V3/5ePHB/snippets.js](/static/storegenerator/themes/V3/5ePHB/snippets.js) | JavaScript | 297 | 7 | 24 | 328 |
| [static/storegenerator/themes/V3/5ePHB/snippets/classfeature.gen.js](/static/storegenerator/themes/V3/5ePHB/snippets/classfeature.gen.js) | JavaScript | 35 | 0 | 15 | 50 |
| [static/storegenerator/themes/V3/5ePHB/snippets/classtable.gen.js](/static/storegenerator/themes/V3/5ePHB/snippets/classtable.gen.js) | JavaScript | 132 | 0 | 7 | 139 |
| [static/storegenerator/themes/V3/5ePHB/snippets/coverpage.gen.js](/static/storegenerator/themes/V3/5ePHB/snippets/coverpage.gen.js) | JavaScript | 127 | 0 | 30 | 157 |
| [static/storegenerator/themes/V3/5ePHB/snippets/fullclass.gen.js](/static/storegenerator/themes/V3/5ePHB/snippets/fullclass.gen.js) | JavaScript | 31 | 0 | 12 | 43 |
| [static/storegenerator/themes/V3/5ePHB/snippets/index.gen.js](/static/storegenerator/themes/V3/5ePHB/snippets/index.gen.js) | JavaScript | 84 | 0 | 1 | 85 |
| [static/storegenerator/themes/V3/5ePHB/snippets/magic.gen.js](/static/storegenerator/themes/V3/5ePHB/snippets/magic.gen.js) | JavaScript | 99 | 0 | 11 | 110 |
| [static/storegenerator/themes/V3/5ePHB/snippets/monsterblock.gen.js](/static/storegenerator/themes/V3/5ePHB/snippets/monsterblock.gen.js) | JavaScript | 169 | 0 | 16 | 185 |
| [static/storegenerator/themes/V3/5ePHB/snippets/quote.gen.js](/static/storegenerator/themes/V3/5ePHB/snippets/quote.gen.js) | JavaScript | 46 | 0 | 6 | 52 |
| [static/storegenerator/themes/V3/5ePHB/snippets/script.gen.js](/static/storegenerator/themes/V3/5ePHB/snippets/script.gen.js) | JavaScript | 42 | 0 | 7 | 49 |
| [static/storegenerator/themes/V3/5ePHB/snippets/tableOfContents.gen.js](/static/storegenerator/themes/V3/5ePHB/snippets/tableOfContents.gen.js) | JavaScript | 81 | 0 | 6 | 87 |
| [static/storegenerator/themes/V3/5ePHB/snippets/watercolor.gen.js](/static/storegenerator/themes/V3/5ePHB/snippets/watercolor.gen.js) | JavaScript | 4 | 0 | 2 | 6 |
| [static/storegenerator/themes/V3/5ePHB/style.less](/static/storegenerator/themes/V3/5ePHB/style.less) | Less | 812 | 91 | 40 | 943 |
| [static/storegenerator/themes/V3/Blank/settings.json](/static/storegenerator/themes/V3/Blank/settings.json) | JSON with Comments | 6 | 0 | 1 | 7 |
| [static/storegenerator/themes/V3/Blank/snippets.js](/static/storegenerator/themes/V3/Blank/snippets.js) | JavaScript | 426 | 6 | 13 | 445 |
| [static/storegenerator/themes/V3/Blank/snippets/footer.gen.js](/static/storegenerator/themes/V3/Blank/snippets/footer.gen.js) | JavaScript | 14 | 0 | 3 | 17 |
| [static/storegenerator/themes/V3/Blank/snippets/imageMask.gen.js](/static/storegenerator/themes/V3/Blank/snippets/imageMask.gen.js) | JavaScript | 40 | 0 | 7 | 47 |
| [static/storegenerator/themes/V3/Blank/snippets/watercolor.gen.js](/static/storegenerator/themes/V3/Blank/snippets/watercolor.gen.js) | JavaScript | 4 | 0 | 2 | 6 |
| [static/storegenerator/themes/V3/Blank/style.less](/static/storegenerator/themes/V3/Blank/style.less) | Less | 404 | 36 | 23 | 463 |
| [static/storegenerator/themes/V3/Journal/settings.json](/static/storegenerator/themes/V3/Journal/settings.json) | JSON with Comments | 6 | 0 | 1 | 7 |
| [static/storegenerator/themes/V3/Journal/snippets.js](/static/storegenerator/themes/V3/Journal/snippets.js) | JavaScript | 2 | 1 | 2 | 5 |
| [static/storegenerator/themes/V3/Journal/style.less](/static/storegenerator/themes/V3/Journal/style.less) | Less | 489 | 51 | 20 | 560 |
| [static/storegenerator/themes/assets/assets.less](/static/storegenerator/themes/assets/assets.less) | Less | 31 | 2 | 2 | 35 |
| [static/storegenerator/themes/assets/coverPageBanner.svg](/static/storegenerator/themes/assets/coverPageBanner.svg) | XML | 1 | 0 | 0 | 1 |
| [static/storegenerator/themes/assets/discordOfManyThings.svg](/static/storegenerator/themes/assets/discordOfManyThings.svg) | XML | 1 | 0 | 0 | 1 |
| [static/storegenerator/themes/assets/horizontalRule.svg](/static/storegenerator/themes/assets/horizontalRule.svg) | XML | 1 | 0 | 0 | 1 |
| [static/storegenerator/themes/assets/naturalCritLogoRed.svg](/static/storegenerator/themes/assets/naturalCritLogoRed.svg) | XML | 1 | 0 | 0 | 1 |
| [static/storegenerator/themes/assets/naturalCritLogoWhite.svg](/static/storegenerator/themes/assets/naturalCritLogoWhite.svg) | XML | 50 | 0 | 1 | 51 |
| [static/storegenerator/themes/assets/partCoverHeaderDMG.svg](/static/storegenerator/themes/assets/partCoverHeaderDMG.svg) | XML | 1 | 0 | 0 | 1 |
| [static/storegenerator/themes/codeMirror/customEditorStyles.less](/static/storegenerator/themes/codeMirror/customEditorStyles.less) | Less | 85 | 3 | 0 | 88 |
| [static/storegenerator/themes/codeMirror/customThemes/darkbrewery-v301.css](/static/storegenerator/themes/codeMirror/customThemes/darkbrewery-v301.css) | CSS | 101 | 20 | 8 | 129 |
| [static/storegenerator/themes/codeMirror/editorThemes.json](/static/storegenerator/themes/codeMirror/editorThemes.json) | JSON | 69 | 0 | 1 | 70 |
| [static/storegenerator/themes/fonts/5e legacy/fonts.less](/static/storegenerator/themes/fonts/5e%20legacy/fonts.less) | Less | 54 | 4 | 4 | 62 |
| [static/storegenerator/themes/fonts/5e/dicefont.less](/static/storegenerator/themes/fonts/5e/dicefont.less) | Less | 114 | 3 | 1 | 118 |
| [static/storegenerator/themes/fonts/5e/dicefont_license.md](/static/storegenerator/themes/fonts/5e/dicefont_license.md) | Markdown | 10 | 0 | 9 | 19 |
| [static/storegenerator/themes/fonts/5e/fonts.less](/static/storegenerator/themes/fonts/5e/fonts.less) | Less | 127 | 5 | 13 | 145 |
| [static/storegenerator/themes/fonts/Journal/fonts.less](/static/storegenerator/themes/fonts/Journal/fonts.less) | Less | 48 | 4 | 7 | 59 |
| [static/storegenerator/themes/fonts/icon fonts/font-icons.less](/static/storegenerator/themes/fonts/icon%20fonts/font-icons.less) | Less | 209 | 7 | 8 | 224 |
| [static/storegenerator/themes/phb.depricated.less](/static/storegenerator/themes/phb.depricated.less) | Less | 26 | 4 | 1 | 31 |
| [static/storegenerator/themes/themes.json](/static/storegenerator/themes/themes.json) | JSON | 40 | 0 | 0 | 40 |
| [storegenerator/__init__.py](/storegenerator/__init__.py) | Python | 0 | 0 | 1 | 1 |
| [storegenerator/block_builder.py](/storegenerator/block_builder.py) | Python | 363 | 27 | 31 | 421 |
| [storegenerator/sd_generator.py](/storegenerator/sd_generator.py) | Python | 12 | 0 | 3 | 15 |
| [storegenerator/store_helper.py](/storegenerator/store_helper.py) | Python | 292 | 10 | 32 | 334 |
| [tests/_cloudflare.py](/tests/_cloudflare.py) | Python | 41 | 6 | 14 | 61 |
| [tests/_store_router.py](/tests/_store_router.py) | Python | 15 | 4 | 7 | 26 |
| [tests/cloudflareR2/_cloudflareR2.py](/tests/cloudflareR2/_cloudflareR2.py) | Python | 143 | 25 | 37 | 205 |
| [tests/cloudflareR2/_r2_config.py](/tests/cloudflareR2/_r2_config.py) | Python | 41 | 3 | 6 | 50 |
| [tests/cloudflareR2/r2_config.py](/tests/cloudflareR2/r2_config.py) | Python | 26 | 14 | 8 | 48 |
| [tests/cloudflareR2/store.html](/tests/cloudflareR2/store.html) | HTML | 621 | 0 | 6 | 627 |
| [tests/conftest.py](/tests/conftest.py) | Python | 26 | 2 | 5 | 33 |
| [tests/firestore/test_firestore.py](/tests/firestore/test_firestore.py) | Python | 66 | 3 | 13 | 82 |
| [tests/rulesLawyer/rulesLawyer_helper.py](/tests/rulesLawyer/rulesLawyer_helper.py) | Python | 102 | 13 | 35 | 150 |
| [tests/rulesLawyer/rulesLawyer_router.py](/tests/rulesLawyer/rulesLawyer_router.py) | Python | 59 | 1 | 13 | 73 |
| [tests/rulesLawyer/test_bot_response.py](/tests/rulesLawyer/test_bot_response.py) | Python | 42 | 2 | 5 | 49 |
| [tests/rulesLawyer/test_embedding_loader.py](/tests/rulesLawyer/test_embedding_loader.py) | Python | 80 | 3 | 9 | 92 |
| [tests/session_managment/test_session_management.py](/tests/session_managment/test_session_management.py) | Python | 140 | 20 | 27 | 187 |
| [tests/storegenerator/block_builder.py](/tests/storegenerator/block_builder.py) | Python | 458 | 29 | 32 | 519 |
| [tests/storegenerator/sd_generator.py](/tests/storegenerator/sd_generator.py) | Python | 12 | 0 | 3 | 15 |
| [tests/storegenerator/store_helper.py](/tests/storegenerator/store_helper.py) | Python | 292 | 10 | 32 | 334 |

[Summary](results.md) / Details / [Diff Summary](diff.md) / [Diff Details](diff-details.md)