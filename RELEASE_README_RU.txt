Mesh Repeater v2.09

Полностью распакуйте ZIP в обычную папку до открытия файлов KiCad.
Откройте нужный проект платы в KiCad 10 с официальными библиотеками:
  POWER: v2/design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pro
  LOGIC: v2/design/MeshRepeater2_Logic/MeshRepeater2_Logic.kicad_pro
  SHIELD: v2/design/MeshRepeater2_Shield/MeshRepeater2_Shield.kicad_pro
Для 3D включите категории «Модели выводные» и «Модели SMD».
Общая схема: shared/schematic/MeshRepeater.kicad_sch
У общей схемы нет собственной PCB; физические платы перечислены выше.
Проверка: python tools/project/release.py check --product v2
Пакет содержит выбранную аппаратную версию и общую схему/профили.
Производственные пакеты, расчёты заказа, исторические снимки и среды сборки исключены.
Проверки CAD не заменяют испытаний образца.
