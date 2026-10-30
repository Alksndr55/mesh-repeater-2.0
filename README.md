# Mesh Repeater v2.09

Исполнение POWER + LOGIC + SHIELD, 90×60 мм. Ведущая электрическая схема — v1.

[Готовый архив KiCad](https://github.com/Alksndr55/mesh-repeater-2.0/releases/download/v2.09/Mesh_Repeater_v2.09_KiCad.zip) · [Страница выпуска](https://github.com/Alksndr55/mesh-repeater-2.0/releases/tag/v2.09)

## Открытие проекта

Полностью распакуйте архив перед открытием. Используйте KiCad 10 с официальными библиотеками; локальные модели и посадочные места включены.

- [POWER](v2/design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pro)
- [LOGIC](v2/design/MeshRepeater2_Logic/MeshRepeater2_Logic.kicad_pro)
- [SHIELD](v2/design/MeshRepeater2_Shield/MeshRepeater2_Shield.kicad_pro)

Общая электрическая схема: [KiCad](shared/schematic/MeshRepeater.kicad_pro), [PDF](shared/output/pdf/MeshRepeater_schematic.pdf).

## Состав выпуска

Исправлены подводы дорожек и острые стыки, удалены лишние GND-дорожки поверх заливки, восстановлены реальные термобарьеры. Земляные vias расположены по сетке 5 мм; местные исключения записаны в `routing_review.json` каждой платы. Расстановка и критические RF/Kelvin-участки сохранены.

Watchdog **v1.00** включён в [v2/design/watchdog_reference](v2/design/watchdog_reference). Исходник и HEX совпадают с [канонической прошивкой](https://github.com/Alksndr55/watchdog/releases/tag/v1.00). Прошивка микросхемы и установка fuse выполняются отдельно.

- [Полный список изменений разводки](docs/ROUTING_RESULT_RU.md)
- [BOM](v2/bom/COMPONENT_BOM.csv) и [сборка](v2/docs/ASSEMBLY_RU.md)
- [Свежие проверки](v2/audit/current/checks.json)
- [Порядок выпуска](docs/WORKFLOW_RU.md), [аппаратные ограничения](docs/LIMITATIONS_RU.md)
- [Лицензия](v2/LICENSE.md)

ERC/DRC и соответствие общей схеме проверены для точных файлов выпуска. Проверка распакованного пакета выполнена независимо. Это инженерный прототип; CAD-проверки не являются испытанием платы.

Каталоги `v2/`, `shared/`, `docs/`, `tools/project/` составляют переносимый проект этого исполнения. Архив другого исполнения, исторические снимки и производственные пакеты в него не включены.

Designed by @Alksndritm.
