const fs=require('fs'),path=require('path');
const sharp=require('C:/Users/Alksndr/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const dir=path.resolve('v2/audit/a3_2026_10_13/power_labels/views');
(async()=>{
  for(const name of ['POWER_front_labels','POWER_back_labels_projected']){
    const svg=fs.readFileSync(path.join(dir,name+'_color.svg'),'utf8')
      .replaceAll('#AFAFAF','#DADADA').replaceAll('#F2EDA1','#111111')
      .replaceAll('#E8B2A7','#111111').replaceAll('#D0D2CD','#777777');
    fs.writeFileSync(path.join(dir,name+'_readable.svg'),svg);
    await sharp(Buffer.from(svg),{density:500}).resize({width:2000})
      .flatten({background:'#FFFFFF'}).png().toFile(path.join(dir,name+'.png'));
    console.log(name+'.png');
  }
})();
