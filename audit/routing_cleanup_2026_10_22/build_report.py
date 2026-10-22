"""Bind the current routing review and visible overview to the saved boards."""
from pathlib import Path
import hashlib, html, json

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'output'
def read(p):return json.loads(p.read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    native=read(HERE/'after/native_summary.json')
    integration=read(HERE/'integration.json')
    results={}
    for n in ['POWER','LOGIC']:
        base=HERE/'review/final'/n
        c=read(base/'comparison.json');before=read(base/'before/summary.json');after=read(base/'after/summary.json')
        assert c['all_nonrouting_invariants_preserved'] and c['all_footprints_and_pad_nets_preserved']
        assert c['remaining_collinear_overlap_pairs']==c['remaining_exact_duplicates']==c['remaining_off_angle']==0
        assert not c['nets_with_minimum_width_reduction']
        assert c['ground_components_after']==c['ground_components_before']==1
        source=ROOT/integration[n]['source']
        assert sha(source)==c['after_sha256']==integration[n]['after_sha256']
        assert all(x['exit_code']==0 for x in native[n]['commands'])
        assert all(native[n]['drc'][k]==0 for k in ['violations','unconnected_items','schematic_parity'])
        assert native[n]['erc']['violations']==0
        results[n]=dict(comparison=c,before=before,after=after)
    result=dict(date='2026-10-22',scope=['POWER','LOGIC'],status='applied_to_main_CAD',
                sources=integration,independent_review=results,native_checks=native,
                independent_acceptance={n:read(HERE/'review/final'/n/'ACCEPTANCE.json') for n in results},
                native_view_visual_review=read(HERE/'review/VISUAL_QA.json'),
                manufacturing_packages_current=False,
                manufacturing_note='Existing A4-FAB2 Rezonit and BOSONSTAR ZIP files describe the 2026-10-16 geometry and have not been regenerated for these routing edits.')
    (HERE/'FINAL_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    rows=[]
    for n,r in results.items():
        b,a,c=r['before'],r['after'],r['comparison']
        vals=[('Сегменты дорожек',b['segments'],a['segments']),
              ('Длина дорожек без GND, мм',f"{b['non_gnd_length_mm']:.2f}",f"{a['non_gnd_length_mm']:.2f}"),
              ('Длина явных дорожек GND, мм',f"{b['gnd_length_mm']:.2f}",f"{a['gnd_length_mm']:.2f}"),
              ('Все переходные отверстия',b['vias'],a['vias']),
              ('Перекрывающиеся пары сегментов',len(b['collinear_overlap_pairs']),len(a['collinear_overlap_pairs'])),
              ('Повороты 90° без GND (узлы с двумя сегментами)',b['non_gnd_bend_histogram'].get('90.0',0),a['non_gnd_bend_histogram'].get('90.0',0))]
        rows.extend(f'<tr><td>{n}</td><td>{label}</td><td>{old}</td><td>{new}</td></tr>' for label,old,new in vals)
    aud='../audit/routing_cleanup_2026_10_22/'
    panels=[]
    for n in results:
        for side,label in [('front','лицевая сторона'),('back','обратная сторона')]:
            ident=f'{n}_{side}'
            stem=f'{n}_routes_{side}.png'
            panels.append(f'''<figure><figcaption>{n} — {label}</figcaption>
<div class="buttons"><button onclick="setView('{ident}','before','{n}','{side}')">До</button><button onclick="setView('{ident}','after','{n}','{side}')">После</button><span id="{ident}_label">После</span></div>
<a id="{ident}_link" href="{aud}views/after/{n}/{stem}"><img id="{ident}" src="{aud}views/after/{n}/{stem}" loading="lazy" alt="{n}: дорожки {label}"></a>
<p><a href="{aud}views/after/{n}/{n}_copper_{side}.png">Фактическая медь с заливкой</a></p></figure>''')
    template='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mesh Repeater 2.0 A5 — исправление трассировки 22.10.2026</title>
<style>body{margin:0;background:#f3f5f7;color:#192c38;font:16px/1.5 system-ui,sans-serif}main{max-width:1500px;margin:auto;padding:24px}h1{font-size:29px;margin:0 0 12px}h2{font-size:22px}a{color:#075a86}nav{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}nav a,button{background:white;border:1px solid #b7c7d0;padding:8px 13px;border-radius:4px;color:#075a86;cursor:pointer}table{border-collapse:collapse;width:100%;background:white}td,th{border:1px solid #c7d1d8;padding:8px;text-align:left}th{background:#e0eaf0}.note{background:#fff0ce;border-left:5px solid #b87d14;padding:12px 16px}.ok{background:#e4f4eb;border-left:5px solid #26734d;padding:12px 16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:18px}figure{margin:0;background:white;border:1px solid #c5d2da;border-radius:5px;overflow:hidden}figcaption{font-weight:600;padding:12px}.buttons{display:flex;align-items:center;gap:10px;padding:0 12px 12px}figure p{padding:0 12px}img{width:100%;display:block;height:auto}.hash{font:12px monospace;overflow-wrap:anywhere}@media(max-width:650px){main{padding:12px}.grid{grid-template-columns:1fr}table{font-size:12px}td,th{padding:5px}}</style>
<main><h1>Mesh Repeater 2.0 A5 · исправление трассировки</h1><p>22 октября 2026 · основные проекты POWER и LOGIC · платы 90×60 мм</p>
<p class="ok">Исправления внесены в исходные файлы KiCad. Убраны перекрывающиеся сегменты и лишние земляные связи поверх заливки; мешавшие трассам переходы GND перенесены или удалены. Маршруты выпрямлены. Схема, номиналы, положения компонентов, GPIO, межплатные соединения и ISP J10 сохранены.</p>
<nav><a href="../design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pro">Проект POWER</a><a href="../design/MeshRepeater2_Logic/MeshRepeater2_Logic.kicad_pro">Проект LOGIC</a><a href="../design/MeshRepeater2_Power/MeshRepeater2_Power.kicad_pcb">Плата POWER</a><a href="../design/MeshRepeater2_Logic/MeshRepeater2_Logic.kicad_pcb">Плата LOGIC</a><a href="__AUDIT_BASE__FINAL_AUDIT.json">Подробный протокол</a><a href="../docs/LICENSING_RU_EN.md">Лицензия и личный заказ плат</a><a href="https://github.com/Alksndr55/mesh-repeater-2.0/releases/tag/v2.0-a5">Релиз A5</a></nav>
<p>Повторные native DRC после перезаливки: 0 нарушений, 0 неразведённых цепей, 0 расхождений со схемой. ERC обеих схем: 0 нарушений. Независимая геометрическая проверка не нашла дублирующихся и частично перекрывающихся сегментов. Земля каждой платы остаётся единой связной сетью через оба слоя; ширины дорожек не уменьшены.</p>
<p class="note"><b>Производственные архивы A4-FAB2 от 16.10.2026 относятся к прежней разводке.</b> После этих изменений их нужно пересоздать перед новым заказом. Они сохранены как предыдущий снимок. Перед USB по-прежнему необходимо снять J11 на POWER.</p>
<h2>Измеренное сравнение</h2><table><thead><tr><th>Плата</th><th>Параметр</th><th>До</th><th>После</th></tr></thead><tbody>ROWS</tbody></table>
<p>Длина без GND приведена отдельно: удаление дорожек поверх земляной заливки не выдается за сокращение сигнальных маршрутов. Повороты подсчитаны в узлах с двумя сегментами одной цепи и слоя; площадки и ответвления не входят в этот счёт.</p>
<h2>Дорожки до и после</h2><p>Переключатели показывают экспорт KiCad из копий с отключённой заливкой, чтобы были видны сами дорожки и переходы. Эти иллюстрации не предназначены для изготовления. По ссылке под каждым видом доступна фактическая медь с заливкой.</p><div class="grid">PANELS</div>
<h2>Границы проверки</h2><p>Проверена геометрия сохранённых файлов, электрическая связность и соответствие схеме. Короткие локальные земляные возвраты у преобразователей и развязывающих конденсаторов, Kelvin-подводы INA219 и RF-участок сохранены. Измерение помех, нагрева и стабильности на собранной плате в эту проверку не входит.</p>
<details><summary>SHA256 текущих плат</summary>HASHES</details><p>Designed by @Alksndritm. Собственные материалы — <a href="../LICENSE.md">CC BY-NC-SA 4.0</a>. Личный заказ плат у изготовителя разрешён; коммерческий выпуск и продажа требуют письменного разрешения автора. <a href="../THIRD_PARTY_NOTICES.md">Сторонние лицензии сохранены.</a></p></main>
<script>function setView(id,phase,name,side){const url='__AUDIT_BASE__views/'+phase+'/'+name+'/'+name+'_routes_'+side+'.png';document.getElementById(id).src=url;document.getElementById(id+'_link').href=url;document.getElementById(id+'_label').textContent=phase==='before'?'До':'После';}</script></html>'''
    hashes=''.join(f'<p>{n}<br><span class="hash">{r["after"]["sha256"]}</span></p>' for n,r in results.items())
    page=template.replace('ROWS',''.join(rows)).replace('PANELS',''.join(panels)).replace('HASHES',hashes).replace('__AUDIT_BASE__',aud)
    for path in [OUT/'V2_ROUTING_CLEANUP_2026_10_22_RU.html',OUT/'V2_OVERVIEW_RU.html']:
        path.write_text(page,'utf-8')
    notice='''ТЕКУЩИЙ CAD И ПРОИЗВОДСТВЕННЫЕ АРХИВЫ\n22.10.2026\n\nВ основные платы POWER и LOGIC внесены изменения трассировки.\nСуществующие архивы A4-FAB2 от 16.10.2026 (Резонит и BOSONSTAR)\nотносятся к предыдущей разводке и не содержат этих исправлений.\nПеред заказом актуальной платы пакет нужно пересоздать.\n\nПроверки и актуальные исходники:\n../output/V2_OVERVIEW_RU.html\n../audit/routing_cleanup_2026_10_22/FINAL_AUDIT.json\n'''
    (ROOT/'manufacturing/CURRENT_CAD_NOTICE_RU.txt').write_text(notice,'utf-8')
    readme_path=ROOT/'README.md'
    readme=readme_path.read_text('utf-8')
    banner='**22.10.2026 — текущие правки трассировки POWER и LOGIC.** Удалены перекрытия и лишние GND-связи, перенесены мешавшие дорожкам земляные переходы, сокращены изгибы и длины. [Виды до/после и свежие проверки](output/V2_ROUTING_CLEANUP_2026_10_22_RU.html). Производственные ZIP A4-FAB2 от 16.10.2026 содержат прежнюю геометрию; для заказа обновлённой платы их необходимо пересоздать.\n\n'
    anchor='**Designed by @Alksndritm**\n\n'
    if banner not in readme:
        assert readme.count(anchor)==1
        readme=readme.replace(anchor,anchor+banner,1)
    replacements={
      'Рабочая ревизия **V2.0-A4-FAB2**.':'Рабочий проект — A4 с изменениями трассировки от 22.10.2026 поверх снимка A4-FAB2.',
      '[Перенос независимо принятых исправлений](audit/routing_full_2026_10_16/integration.json) подтверждает соответствие основных плат производственному пакету.':'[Перенос правок 22.10.2026](audit/routing_cleanup_2026_10_22/integration.json) фиксирует текущие исходники. Производственные архивы FAB2 соответствуют предыдущему снимку от 16.10.2026.',
      '[Пакет для заказа 5 комплектов POWER + LOGIC + SHIELD]':'[Предыдущий пакет FAB2: 5 комплектов POWER + LOGIC + SHIELD]',
      'Архив содержит текущие Gerber/Excellon, технические требования и чертежи;':'Архив содержит Gerber/Excellon, технические требования и чертежи снимка от 16.10.2026;',
      '[обзор A4-FAB2 с видами обеих сторон из Gerber]':'[актуальный обзор с дорожками до/после и видами фактической меди]',
      '[Текущие проверки A4-FAB2]':'[Проверки предыдущего снимка A4-FAB2]',
      'Свежие проверки основных файлов A4-FAB2 от 16.10.2026:':'Проверки снимка A4-FAB2 от 16.10.2026:'
    }
    for old,new in replacements.items():
        if old in readme:readme=readme.replace(old,new,1)
    readme_path.write_text(readme,'utf-8',newline='\n')
    print(json.dumps({n:{k:r['comparison'][k] for k in ['removed_segments','reduced_non_gnd_length_mm','removed_gnd_track_length_mm','remaining_collinear_overlap_pairs']} for n,r in results.items()},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
