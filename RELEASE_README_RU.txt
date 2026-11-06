Mesh Repeater v2.10

Полностью распакуйте ZIP в обычную папку до запуска START.cmd или открытия файлов.
Portable NexusBV 0.9 для Windows 10/11 x64 включён; установка не требуется.
Откройте START.cmd в корне распакованного пакета и выберите плату и химию.
Или запустите START_<плата>_<химия>.cmd: CAD и PDF этой платы откроются вместе.
Для SHIELD открывается только CAD. Не запускайте команды прямо из ZIP.
Сохраняйте структуру папок пакета: программа и схемы нужны для запуска.
Откройте нужный проект платы в KiCad 10:
  POWER: v2/design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pro
  LOGIC: v2/design/MeshRepeater2_Logic/MeshRepeater2_Logic.kicad_pro
  SHIELD: v2/design/MeshRepeater2_Shield/MeshRepeater2_Shield.kicad_pro
Все используемые 3D-модели включены и используют относительные пути.
Для 3D включите категории «Модели выводные» и «Модели SMD».
Общая схема: shared/schematic/MeshRepeater.kicad_sch
У общей схемы нет собственной PCB; физические платы перечислены выше.
Boardview с номиналами: откройте CAD через File → Open в NexusBV:
  v2/output/current/POWER/Mesh_Repeater_v2.10_POWER_NaIon_COLD.cad
  v2/output/current/POWER/Mesh_Repeater_v2.10_POWER_LTO_2S.cad
  v2/output/current/LOGIC/Mesh_Repeater_v2.10_LOGIC_NaIon_COLD.cad
  v2/output/current/LOGIC/Mesh_Repeater_v2.10_LOGIC_LTO_2S.cad
  v2/output/current/SHIELD/Mesh_Repeater_v2.10_SHIELD_NaIon_COLD.cad
  v2/output/current/SHIELD/Mesh_Repeater_v2.10_SHIELD_LTO_2S.cad
NaIon_COLD — натрий с COLD-защитой; LTO_2S — LTO 2S.
Номиналы соответствуют сборке; DNP означает «не устанавливать».
Top / Bottom — стороны; номинал виден в Info и карточке компонента.
Для перехода со схемы дважды щёлкните по телу символа или его обозначению
(например R15) в PDF внутри NexusBV. Имена цепей также доступны для поиска.
Надписи внутри символа сохраняют свой поиск: нажимайте по свободной части тела.
PDF схемы находится рядом с CAD: <плата>_schematic.pdf; для SHIELD схемы нет.
PDF показывает общую схему; номиналы/FIT выбранной химии смотрите в CAD и BOM.
Проверка: python tools/project/release.py check --product v2
Пакет содержит выбранную аппаратную версию и общую схему/профили.
Производственные пакеты, расчёты заказа, исторические снимки и среды сборки исключены.
Проверки CAD не заменяют испытаний образца.
