"use strict";

const wordsPerRound = 6;
const tints = ["#c7dfac","#f7d5a7","#b9dcd9","#ddcde7","#e9dc98","#c0d5ef"];
const $ = id => document.getElementById(id);
const lastWords = new Map();
let currentRound;
let selectedTrail = 0, activePointer = null;
let anchor = null, cursor = null, keyboardCell = 0, hintWord = null;
let player = null, sound = true, stamps = [];
try {
  sound = localStorage.getItem("onenglish.wordtrails.sound") !== "off";
} catch {}
const trail = () => trails[selectedTrail];
const round = () => currentRound;

function shuffle(values) {
  const list = [...values];
  for (let i = list.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [list[i], list[j]] = [list[j], list[i]];
  }
  return list;
}

function buildPuzzle(course, targets) {
  const n = course.size, letters = Array(n*n).fill(""), paths = {};
  const entries = shuffle(targets).sort((a,b) => b[0].length - a[0].length);
  for (const [word] of entries) {
    const options = [];
    for (let r=0; r<n; r++) for (let c=0; c<n; c++) {
      for (const [dy,dx] of course.directions) {
        const endR = r+dy*(word.length-1), endC = c+dx*(word.length-1);
        if (endR<0 || endC<0 || endR>=n || endC>=n) continue;
        const path = Array.from(word, (_,i) => (r+dy*i)*n+c+dx*i);
        if (path.every((p,i) => !letters[p] || letters[p]===word[i])) options.push(path);
      }
    }
    if (!options.length) {
      // Separate rows always fit every word in these courses.
      letters.fill("");
      const rows = shuffle(Array.from({length:n},(_,i)=>i));
      entries.forEach(([w],i) => {
        const start = rows[i]*n + Math.floor(Math.random()*(n-w.length+1));
        paths[w] = Array.from(w, (ch,j) => { letters[start+j]=ch; return start+j });
      });
      break;
    }
    const path = options[Math.floor(Math.random()*options.length)];
    path.forEach((p,i) => letters[p]=word[i]);
    paths[word] = path;
  }
  return {letters:letters.map(ch => ch || String.fromCharCode(65+Math.floor(Math.random()*26))), paths};
}

function newRound(course) {
  const key = "onenglish.wordtrails.last." + playerScope + "." + course.title;
  let previous = lastWords.get(key) || [];
  try {
    const stored = JSON.parse(localStorage.getItem(key));
    if (Array.isArray(stored)) previous = stored;
  } catch {}

  // Reserve half the round for words absent from the previous visit.
  const fresh = shuffle(course.entries.filter(([word]) => !previous.includes(word)));
  const reserved = fresh.slice(0, Math.ceil(wordsPerRound / 2));
  const rest = shuffle(course.entries.filter(entry => !reserved.includes(entry)));
  const entries = shuffle([...reserved, ...rest.slice(0, wordsPerRound - reserved.length)]);
  const words = entries.map(([word]) => word);
  lastWords.set(key, words);
  try { localStorage.setItem(key, JSON.stringify(words)) } catch {}

  return { ...buildPuzzle(course, entries), entries, id:crypto.randomUUID(), attempts:{}, found:new Map(), phase:"search",
    note:"단어를 찾으면 이곳에 예문이 나타나요. ‘복습’을 누르면 문장 전체를 들을 수 있어요.",
    queue:shuffle(entries), question:0, firstTry:0, missed:new Set(), answered:false, choices:[] };
}
function makeButton(label, handler, style="") {
  const b = document.createElement("button");
  b.type = "button"; b.textContent=label; b.className=style; b.onclick=handler;
  return b;
}
function stopAudio() {
  if (player) { player.pause(); player = null }
}
function playAudio(path) {
  stopAudio();
  if (!sound) return;
  const audio = new Audio(path);
  player = audio;
  audio.play().catch(() => {
    if (player===audio) $("feedback").textContent="발음 파일을 재생할 수 없어요.";
  });
}
function sentence(entry) {
  return entry[2].replace("___", entry[0]==="EARTH" ? "Earth" : entry[0].toLowerCase());
}
function playSentence(entry) {
  playAudio("voice/sentences/"+entry[0].toLowerCase()+".mp3");
}
function inspectWord(entry) {
  round().note=sentence(entry)+"\n"+entry[3];
  $("note").textContent=round().note;
  playSentence(entry);
}
function renderNavigation() {
  $("trails").replaceChildren(...trails.map((item,i) => {
    const b=makeButton(item.ko+(stamps.includes(i) ? " ✓" : ""), () => openTrail(i));
    b.title=item.ko+" 새 퍼즐 시작";
    b.setAttribute("aria-current",String(i===selectedTrail)); return b;
  }));
}
function renderNotebook() {
  const s=round(), entries=s.entries;
  $("targets").replaceChildren(...entries.map(([word]) => {
    const label=document.createElement("span");
    label.textContent=word;
    if(s.found.has(word)) label.className="collected";
    return label;
  }));
  $("count").textContent=s.found.size+" / "+entries.length;
  $("fill").style.width=(s.found.size/entries.length*100)+"%";
  $("words").replaceChildren(...entries.map((entry,i) => {
    const found=s.found.has(entry[0]), row=document.createElement("div");
    row.className="word-row"+(found ? " logged" : ""); row.style.setProperty("--tint",tints[i]);
    const dot=document.createElement("span"), name=document.createElement("span"), meaning=document.createElement("span");
    dot.className="swatch"; dot.textContent=found ? "✓" : "";
    name.className="word-name"; name.textContent=entry[0];
    meaning.className="meaning"; meaning.textContent=entry[1];
    row.append(dot,name,meaning);
    if(found) {
      const listen=makeButton("복습",() => inspectWord(entry),"listen");
      listen.setAttribute("aria-label",entry[0]+" 예문 다시 듣기"); row.append(listen);
    }
    return row;
  }));
  $("note").textContent=s.note;
}
function line(a,b) {
  if (a===null || b===null) return [];
  const n=trail().size, dr=Math.floor(b/n)-Math.floor(a/n), dc=b%n-a%n;
  if (dr && dc && Math.abs(dr)!==Math.abs(dc)) return [];
  return Array.from({length:Math.max(Math.abs(dr),Math.abs(dc))+1},(_,i) => a+i*(Math.sign(dr)*n+Math.sign(dc)));
}
function paintBoard() {
  const selected=new Set(line(anchor,cursor));
  if(anchor!==null) selected.add(anchor);
  const foundColors=new Map();
  round().entries.forEach(([w],i) => round().found.get(w)?.forEach(p=>foundColors.set(p,tints[i])));
  const hintStart=hintWord===null ? null : round().paths[hintWord][0];
  Array.from($("board").children).forEach((b,i) => {
    b.className="cell";
    if (foundColors.has(i)) { b.classList.add("found"); b.style.setProperty("--tint",foundColors.get(i)) }
    b.classList.toggle("picked",selected.has(i)); b.classList.toggle("hinted",i===hintStart);
    b.tabIndex=i===keyboardCell ? 0 : -1;
  });
}
function renderBoard() {
  const board=$("board"), n=trail().size;
  board.style.setProperty("--size",n);
  board.replaceChildren(...round().letters.map((ch,i) => {
    const cell=document.createElement("button");
    cell.textContent=ch; cell.dataset.index=i; cell.type="button";
    cell.setAttribute("aria-label",(Math.floor(i/n)+1)+"행 "+(i%n+1)+"열 "+ch);
    return cell;
  }));
  paintBoard();
}
function resetSelection() { anchor=null; cursor=null; activePointer=null }
function submit(end) {
  const path=line(anchor,end), s=round();
  const word=path.map(i=>s.letters[i]).join("");
  const backwards=Array.from(word).reverse().join("");
  const entry=round().entries.find(([w])=>w===word || w===backwards);
  resetSelection();
  if (entry && !s.found.has(entry[0])) {
    s.found.set(entry[0],path); hintWord=null;
    $("feedback").textContent=entry[0]+" 발견!";
    s.note=sentence(entry)+"\n"+entry[3];
    playAudio("voice/words/"+entry[0].toLowerCase()+".mp3"); renderNotebook();
    if (s.found.size===s.entries.length) {
      s.phase="ready"; renderPhase(); $("study").querySelector("button").focus(); return;
    }
  } else {
    $("feedback").textContent=entry ? "이미 찾은 단어예요." : "다시 살펴보세요. 단어의 양 끝을 일직선으로 이어 주세요.";
  }
  paintBoard();
}
function pointerCell(event) {
  const element=document.elementFromPoint(event.clientX,event.clientY);
  return element?.parentElement===$("board") ? Number(element.dataset.index) : null;
}
const board=$("board");
board.onpointerdown=event => {
  const i=pointerCell(event);
  if(i===null || activePointer || event.button!==0) return;
  activePointer={id:event.pointerId,second:anchor!==null};
  anchor=anchor??i; cursor=i; keyboardCell=i;
  board.setPointerCapture(event.pointerId); paintBoard();
};
board.onpointermove=event => {
  if(activePointer?.id!==event.pointerId) return;
  const i=pointerCell(event);
  if(i!==cursor) { cursor=i; paintBoard() }
};
board.onpointerup=event => {
  if(activePointer?.id!==event.pointerId) return;
  const i=pointerCell(event), second=activePointer.second;
  activePointer=null;
  if(i===null || (second && i===anchor)) { resetSelection(); paintBoard() }
  else if(i!==anchor) submit(i);
};
board.onpointercancel=() => { resetSelection(); paintBoard() };
board.onkeydown=event => {
  if(!event.target.matches(".cell")) return;
  const n=trail().size, i=Number(event.target.dataset.index);
  const directions={ArrowLeft:[0,-1],ArrowRight:[0,1],ArrowUp:[-1,0],ArrowDown:[1,0]};
  if(directions[event.key]) {
    const [dr,dc]=directions[event.key], r=Math.floor(i/n)+dr,c=i%n+dc;
    event.preventDefault();
    if(r<0 || c<0 || r>=n || c>=n) return;
    keyboardCell=r*n+c;
    if(anchor!==null) cursor=keyboardCell;
    paintBoard(); board.children[keyboardCell].focus();
  } else if(["Enter"," ","Escape"].includes(event.key)) {
    event.preventDefault();
    if(event.key==="Escape" || i===anchor) resetSelection();
    else if(anchor===null) { anchor=i; cursor=i }
    else { submit(i); return }
    paintBoard();
  }
};
$("hint").onclick=() => {
  hintWord=round().entries.find(([w])=>!round().found.has(w))[0];
  $("feedback").textContent=hintWord+"의 첫 글자를 테두리로 표시했어요."; paintBoard();
};

function showStudy(heading,body) {
  const box=document.createElement("div"), title=document.createElement("h3"), p=document.createElement("p");
  box.className="study-box"; title.textContent=heading; p.textContent=body;
  box.append(title,p); $("study").replaceChildren(box);
  return box;
}
function nextQuestion() {
  const s=round(), entry=s.queue[s.question];
  const others=shuffle(s.entries.filter(e=>e!==entry)).slice(0,2);
  s.choices=shuffle([entry,...others]); s.missed.clear(); s.answered=false; s.phase="quiz";
  renderPhase(); $("study").querySelector("button")?.focus();
  playSentence(entry);
}
function finish() {
  const s=round();
  s.phase="done";
  sendResult(s, selectedTrail);
  renderNavigation(); renderPhase();
  $("feedback").focus();
}
function answer(choice) {
  const s=round(), entry=s.queue[s.question];
  if(s.answered || s.missed.has(choice[0])) return;
  (s.attempts[entry[0]] ??= []).push(choice[0]);
  if(choice!==entry) {
    s.missed.add(choice[0]); renderPhase();
    $("feedback").textContent=choice[0]+"의 뜻은 ‘"+choice[1]+"’예요. 다시 골라보세요.";
    $("study").querySelector("button:not(:disabled)")?.focus(); return;
  }
  if(!s.missed.size) s.firstTry++;
  s.answered=true; inspectWord(entry); renderPhase();
  $("study").querySelector("button").focus();
}
function renderPhase() {
  const course=trail(), s=round(), searching=s.phase==="search";
  board.hidden=!searching; $("study").hidden=searching; $("hint").hidden=!searching;
  $("targets").hidden=!searching;
  $("feedback").textContent="";
  if(searching) {
    $("board-title").textContent="단어 찾기"; $("dimension").textContent=course.size+" × "+course.size;
    $("instruction").textContent="양 끝을 누르거나 드래그하세요. "+course.guide;
    renderBoard(); return;
  }
  $("dimension").textContent="";
  if(s.phase==="ready") {
    $("board-title").textContent="탐험 완료"; $("instruction").textContent=s.entries.length+"개 단어를 모두 찾았어요.";
    const box=showStudy("문장에서도 찾을 수 있을까요?","방금 만난 단어로 문장 "+s.entries.length+"개의 빈칸을 채워 보세요.");
    box.append(makeButton("문장 복습 시작",nextQuestion,"primary"));
  } else if(s.phase==="quiz") {
    const entry=s.queue[s.question];
    $("board-title").textContent="문장 복습"; $("dimension").textContent=(s.question+1)+" / "+s.queue.length;
    $("instruction").textContent=s.answered ? "문장을 소리 내어 읽어 보세요." : "우리말 뜻을 보고 빈칸에 들어갈 단어를 골라보세요.";
    const box=showStudy(s.answered ? sentence(entry) : entry[2],entry[3]);
    if(s.answered) {
      box.append(makeButton(s.question+1===s.queue.length ? "탐험 결과 보기" : "다음 문장",() => {
        s.question++; s.question===s.queue.length ? finish() : nextQuestion();
      },"primary"));
      $("feedback").textContent="정답이에요!";
    } else {
      const options=document.createElement("div"); options.className="options";
      s.choices.forEach(choice => {
        const b=makeButton(choice[0],()=>answer(choice),"option"); b.disabled=s.missed.has(choice[0]); options.append(b);
      });
      box.append(options);
    }
    const listen=makeButton("문장 다시 듣기",()=>playSentence(entry),"quiet sentence-replay");
    listen.disabled=!sound;
    box.append(listen);
  } else {
    $("board-title").textContent="탐험 기록"; $("instruction").textContent=course.ko+" 완주 도장을 받았어요.";
    const box=showStudy(course.title+" ✓","단어 "+s.entries.length+"개 발견 · 첫 시도에 맞힌 문장 "+s.firstTry+" / "+s.queue.length);
    const buttons=document.createElement("div"); buttons.className="actions";
    buttons.append(makeButton("새 퍼즐로 다시 하기",() => {
      openTrail(selectedTrail);
    },"quiet"),makeButton("다음 코스 탐험",()=>openTrail((selectedTrail+1)%trails.length),"primary"));
    box.append(buttons);
    $("feedback").textContent = pendingResult ? "점수를 저장하고 있어요." : "내 점수판에 저장했어요.";
    buttons.querySelectorAll("button").forEach(b => b.disabled = Boolean(pendingResult));
  }
}
function openTrail(index) {
  if (pendingResult) return;
  stopAudio(); selectedTrail=index;
  const c=trail(); currentRound=newRound(c);
  resetSelection(); hintWord=null; keyboardCell=0;
  document.body.style.setProperty("--sky",c.sky);
  document.body.style.setProperty("--hero-ink",c.ink);
  $("title").textContent=c.title; $("subtitle").textContent=c.mood;
  $("edition").textContent="TRAIL "+String(index+1).padStart(2,"0")+" / "+trails.length;
  drawLandscape($("scenery"),index,c.sky); renderNavigation(); renderNotebook(); renderPhase();
}
function renderSound() {
  $("sound").textContent=sound ? "소리 켜짐" : "소리 꺼짐"; $("sound").setAttribute("aria-pressed",String(sound));
}
$("sound").onclick=() => {
  sound=!sound; if(!sound) stopAudio();
  try { localStorage.setItem("onenglish.wordtrails.sound",sound ? "on" : "off") } catch {}
  renderSound();
  const replay=$("study").querySelector(".sentence-replay");
  if(replay) replay.disabled=!sound;
};
$("help").onclick=()=> $("guide").showModal();
renderSound();
connectGame();
