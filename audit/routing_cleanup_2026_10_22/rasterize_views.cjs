const fs = require('fs');
const path = require('path');
const sharp = require('C:/Users/Alksndr/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const base = path.join(__dirname,'views');
async function visit(dir) {
  for (const item of fs.readdirSync(dir,{withFileTypes:true})) {
    const file=path.join(dir,item.name);
    if(item.isDirectory()) await visit(file);
    else if(item.name.endsWith('.svg')) {
      await sharp(file,{density:300}).flatten({background:'#ffffff'}).resize({width:1800}).png().toFile(file.slice(0,-4)+'.png');
    }
  }
}
visit(base).then(()=>process.stdout.write('Native SVG views rasterized\n')).catch(e=>{process.stderr.write(String(e));process.exit(1)});
