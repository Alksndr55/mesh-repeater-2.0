# Mesh Repeater v2.06

Designed by @Alksndritm. Исполнение POWER + LOGIC + SHIELD, платы 90×60 мм. Электрические изменения следуют ведущей v1, разводка адаптирована к двум рабочим платам. Общая схема содержит 150 функциональных позиций; текущая BOM POWER/LOGIC — 161 позиция и три варианта сборки. Прежнее обозначение этой редакции — A6.

[Скачать готовый KiCad ZIP](https://github.com/Alksndr55/mesh-repeater-2.0/releases/download/v2.06/Mesh_Repeater_v2.06_KiCad.zip) · [SHA256](https://github.com/Alksndr55/mesh-repeater-2.0/releases/download/v2.06/SHA256SUMS.txt) · [Описание выпуска](https://github.com/Alksndr55/mesh-repeater-2.0/releases/tag/v2.06).

- Открыть в KiCad: [POWER](v2/design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pro), [LOGIC](v2/design/MeshRepeater2_Logic/MeshRepeater2_Logic.kicad_pro), [SHIELD](v2/design/MeshRepeater2_Shield/MeshRepeater2_Shield.kicad_pro).
- [Общая электрическая схема](shared/schematic/MeshRepeater.kicad_pro), [PDF](shared/output/pdf/MeshRepeater_schematic.pdf), [физические профили](shared/variants.json).
- [BOM](v2/bom/COMPONENT_BOM.csv), [сборка v2](v2/docs/ASSEMBLY_RU.md), [механика](v2/docs/MECHANICS_RU.md), [общая сборка](docs/ASSEMBLY_COMMON_RU.md).
- [Свежие проверки CAD](v2/audit/current/checks.json), [проверка BOM](v2/audit/current/bom.json), [состав выпуска](RELEASE_MANIFEST.json).
- [Единый процесс выпуска](docs/WORKFLOW_RU.md), [лицензия](v2/LICENSE.md).

Для редактирования нужен KiCad 10 со стандартными библиотеками. Локальные библиотеки, модели, watchdog и текущие проверяющие команды входят в проект. Производственный экспорт выполняется отдельно.

Инженерный прототип. Нулевые ERC/DRC не заменяют испытаний собранного стека. Перед USB снять J11 на POWER; доработка Nice!Nano и принятые ограничения LTO сохраняются. [Полный перечень ограничений](docs/LIMITATIONS_RU.md).
