# Mesh Repeater v2.11

Designed by @Alksndritm. Текущее исполнение общего проекта.
Электрические изменения следуют ведущей v1; разводка адаптирована к двум платам.
C65 (100 нФ, 0805) расположен на LOGIC со стороны NiceNano у R33 и подключён
между MCU_RESET и GND. Следующий номер — v2.12.

[POWER](design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pro) · [LOGIC](design/MeshRepeater2_Logic/MeshRepeater2_Logic.kicad_pro) · [SHIELD](design/MeshRepeater2_Shield/MeshRepeater2_Shield.kicad_pro)

[Общая схема](../shared/schematic/MeshRepeater.kicad_pro) ·
[BOM](bom/COMPONENT_BOM.csv) · [Сборка](docs/ASSEMBLY_RU.md) ·
[Порядок выпуска](../docs/WORKFLOW_RU.md) · [Лицензия](LICENSE.md).

Текущие экспорты находятся в output/current, проверки — в audit/current.
Версия и состав задаются корневым project.json. CAD остаётся редактируемым;
общий процесс выпуска сохраняет геометрию и проверяет соответствие общей схеме.
Опубликованные исторические теги сохраняют свои прежние имена.

Дорожки и GND-переходы приведены к [общим правилам](../docs/ROUTING_RULES_RU.md)
с адаптацией к POWER/LOGIC. Включён [watchdog v1.00](design/watchdog_reference/INTEGRATION_RU.txt)
с каноническими исходником и HEX; LFUSE=0x73, HFUSE=0xFB, ISP 100 мкс.
Локальный архив этого выпуска создаётся в `../releases/v2.10/`.
[Результат разводки и исключения сетки](../docs/ROUTING_RESULT_RU.md).
