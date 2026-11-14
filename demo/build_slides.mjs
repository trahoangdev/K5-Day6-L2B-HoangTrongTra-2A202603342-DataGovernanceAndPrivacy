// Authoring dependency: bundled @oai/artifact-tool. The lab pipeline does not need Node.
// Usage: node demo/build_slides.mjs <artifact-tool module path> <skill dir> <runtime python>
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const [modulePath, skillDir, runtimePython] = process.argv.slice(2);
if (!runtimePython) throw new Error('Pass bundled artifact-tool path, skill directory, runtime Python');
process.env.RUNTIME_NODE_MODULES ??= path.resolve(path.dirname(modulePath), '../../..');
const { Presentation, PresentationFile } = await import(pathToFileURL(modulePath).href);
const root = process.cwd();
const build = path.join(root, 'out/submission/slides-build');
await fs.mkdir(build, {recursive: true});
const source = JSON.parse(await fs.readFile('demo/slides_source.json', 'utf8'));
const b = JSON.parse(await fs.readFile('reports/metrics_baseline.json', 'utf8'));
const p = JSON.parse(await fs.readFile('reports/metrics_poc.json', 'utf8'));
const deck = Presentation.create({slideSize:{width:1280,height:720}});
const font = 'Arial';
function text(slide, content, x,y,w,h,size=28,color='#172033',bold=false) {
  const s=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},
    fill:'none',line:{fill:'none',width:0}});
  s.text=content;
  s.text.style={fontFamily:font,fontSize:size,color,bold};
  return s;
}
for (const [i,data] of source.entries()) {
  const slide=deck.slides.add();
  slide.background.fill=i===0?'#101a2e':'#f8fafc';
  slide.speakerNotes.text=data.notes;
  if(i===0) {
    text(slide,data.title,64,140,600,165,66,'#ffffff',true);
    text(slide,data.body.join('\n\n'),68,350,580,245,28,'#e2e8f0');
    slide.images.add({blob:new Uint8Array(await fs.readFile(path.join(root,'fixtures/t02_raw_qc/images/img_18_1.jpg'))),contentType:'image/jpeg',
      alt:'Ảnh đêm synthetic hữu ích, BTC CC0-1.0',fit:'contain',
      position:{left:690,top:180,width:520,height:320}});
    continue;
  }
  text(slide,data.title,64,48,1150,95,48,'#172033',true);
  if(i===2) {
    const metric=(obj,name)=>obj.metrics.find(m=>m.name===name);
    const names=['Defect Recall@B','Precision@B','Defect-type accuracy (GT defects)'];
    const values=[['Metric dev nội bộ','Baseline','PoC'],...names.map(n=>[
      n==='Defect-type accuracy (GT defects)'?'Defect-type accuracy':n,
      metric(b,n).value.toFixed(4),metric(p,n).value.toFixed(4)])];
    const table=slide.tables.add({rows:4,columns:3,left:64,top:165,width:1150,height:250,
      columnWidths:[670,240,240],values});
    table.borders.assign({style:'solid',fill:'#cbd5e1',width:1});
    for(let r=0;r<4;r++)for(let c=0;c<3;c++) {
      const cell=table.getCell(r,c);
      cell.fill=r===0?'#172033':'#ffffff';
      cell.text.style={fontFamily:font,fontSize:27,color:r===0?'#ffffff':'#172033',bold:r===0};
    }
    text(slide,'56 ảnh dev, nhãn AI-assisted đã dùng trong phát triển\n\nPrimary không tăng. Chưa có điểm eval chính thức của BTC.',66,455,1130,170,28);
  } else if(i===3) {
    data.body.forEach((line,j)=>text(slide,line,64,175+j*103,725,95,29));
    slide.images.add({blob:new Uint8Array(await fs.readFile(path.join(root,'fixtures/t02_raw_qc/images/img_17_2.jpg'))),contentType:'image/jpeg',
      alt:'Ảnh synthetic lóa diện rộng đã được Trà chấp thuận RECAPTURE',fit:'contain',
      position:{left:840,top:195,width:375,height:235}});
    text(slide,'img_17_2\nRECAPTURE sau review',845,450,365,100,25,'#475569');
  } else {
    data.body.forEach((line,j)=>text(slide,line,66,173+j*90,1135,85,30));
  }
}
for(const [i,slide] of deck.slides.items.entries()) {
  const png=await deck.export({slide,format:'png',scale:1});
  await fs.writeFile(path.join(build,`slide-${i+1}.png`),new Uint8Array(await png.arrayBuffer()));
}
const candidate=path.join(build,'candidate.pptx');
await (await PresentationFile.exportPptx(deck)).save(candidate);
const { finalizePresentation }=await import(pathToFileURL(path.join(skillDir,'container_tools/artifact_tool_utils.mjs')).href);
const result=await finalizePresentation({
  workspaceDir:root,candidatePath:candidate,finalPath:path.join(root,'demo/team06_t02.pptx'),
  pythonExecutable:runtimePython,
  integrityValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(skillDir,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','3'],
  explicitTotalSlideCount:5,requiredNativeTableOwnerSlides:[3],requiredNativeChartOwnerSlides:[],
  fontPolicy:{basis:'design',families:[font]},verifyArtifactToolImport:true,
  receiptPath:path.join(build,`validation-${Date.now()}.json`),
});
console.log(JSON.stringify(result));
