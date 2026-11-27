// Draw each trail as a small, fixed-resolution travel poster.
function drawLandscape(canvas, theme, sky) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  let seed = 163;
  function random() {
    seed = (seed * 16807) % 2147483647;
    return seed / 2147483647;
  }
  function rect(x, y, width, height, color) {
    ctx.fillStyle = color;
    ctx.fillRect(Math.floor(x), Math.floor(y), width, height);
  }
  function polygon(points, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    points.forEach(([x,y], i) => i ? ctx.lineTo(x,y) : ctx.moveTo(x,y));
    ctx.closePath();
    ctx.fill();
  }
  function disc(x, y, r, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  }
  function ridge(base, amplitude, color, step) {
    const points = [[0,h]];
    for (let x = 0; x <= w + step; x += step) {
      points.push([x, base - random() * amplitude]);
    }
    polygon([...points, [w,h]],color);
  }
  function pine(x,y,size,shade) {
    rect(x-1,y-size,3,size,shade);
    for (let i=1; i<=3; i++) {
      const reach = size * (.09 + i * .055), bottom = y - size * (.72 - i * .2);
      polygon([[x,bottom-size*.47],[x+reach,bottom],[x-reach,bottom]],shade);
    }
  }
  rect(0,0,w,h,sky);
  if(theme>=3) {
    const palettes=[
      ["#d5bb84","#a8ad79","#81915e"],["#c0bdb1","#9ab78a","#79986e"],
      ["#ddb68d","#c89770","#b68769"],["#b4c8ad","#94ac90","#738f77"],
      ["#b3c6cf","#94a9b9","#768e9b"],["#b8cfd8","#93afbb","#eaf1ee"],
      ["#c7bbd0","#a49bb5","#827b91"]
    ];
    const [far,near,ground]=palettes[theme-3];
    disc(389,38,18,"#fff3c8");
    ridge(114,37,far,51); ridge(138,43,near,45); rect(0,140,w,24,ground);
    function cottage(x,y,width,height,wall,roof) {
      rect(x,y,width,height,wall);
      polygon([[x-7,y],[x+width/2,y-25],[x+width+7,y]],roof);
      rect(x+width*.42,y+height-17,10,17,"#565347");
      rect(x+8,y+6,9,8,"#f6dc9a");
    }
    switch(theme) {
      case 3: // Farmyard and fenced pasture
        cottage(445,101,70,39,"#b76248","#784c40");
        rect(529,86,18,54,"#b5ad9a"); disc(538,86,9,"#b5ad9a");
        for(let x=360;x<640;x+=23) rect(x,134,3,16,"#705e44");
        rect(360,138,280,3,"#91754f");
        break;
      case 4: // Greenhouse and flower beds
        cottage(447,95,66,45,"#b1cebd","#709e8d");
        for(let x=451;x<510;x+=13) rect(x,97,2,41,"#f4edd6");
        rect(447,114,66,2,"#f4edd6");
        for(let i=0;i<60;i++) {
          const x=335+random()*310,y=133+random()*25;
          rect(x,y,2,7,"#526e49"); disc(x+1,y,3,["#dfaa9f","#eee0aa","#b498bf"][i%3]);
        }
        break;
      case 5: // Striped market stalls
        for(let i=0;i<3;i++) {
          const x=360+i*84,y=91+i%2*9;
          rect(x+3,y,3,52,"#675444"); rect(x+60,y,3,52,"#675444");
          for(let j=0;j<7;j++) rect(x+j*10,y,10,12,j%2 ? "#fae3be" : ["#b66751","#6f9584","#c99a55"][i]);
          rect(x,y+33,68,13,"#926a4d");
          for(let j=0;j<9;j++) disc(x+j*7+5,y+30,4,j%2 ? "#dba24d" : "#9baf72");
        }
        break;
      case 6: // School with a clock above the entrance
        cottage(427,90,107,50,"#bd8067","#627b78");
        for(let i=0;i<6;i++) rect(432+i*17,99,9,11,"#e7e6c5");
        disc(480,83,8,"#faf2cf"); rect(479,77,2,6,"#514d41"); rect(480,82,4,2,"#514d41");
        rect(552,73,2,69,"#54695c"); polygon([[554,73],[575,78],[554,84]],"#ce8c69");
        break;
      case 7: // Skyline behind the elevated railway
        for(let i=0;i<13;i++) {
          const x=280+i*31,height=27+Math.floor(random()*65);
          rect(x,140-height,26,height,i%2 ? "#748b9b" : "#879ba6");
          for(let y=146-height;y<133;y+=12) for(let col=0;col<3;col++) rect(x+4+7*col,y,3,5,"#e3d4a8");
        }
        rect(304,123,336,6,"#495f67");
        for(let x=327;x<640;x+=61) rect(x,128,6,21,"#657c82");
        rect(416,110,79,12,"#b86350");
        for(let x=421;x<491;x+=10) rect(x,112,6,4,"#f1dba7");
        break;
      case 8: // Snow peaks and a mountain hut
        for(const [x,y,r] of [[400,53,88],[515,22,101],[594,63,84]]) {
          polygon([[x-r,139],[x,y],[x+r,139]],"#8da6b4");
          polygon([[x-r*.37,y+(139-y)*.37],[x,y],[x+r*.37,y+(139-y)*.37],[x+5,y+22],[x-5,y+29]],"#f5f7ed");
        }
        cottage(462,120,41,23,"#97765e","#f3f2e5");
        for(let i=0;i<18;i++) pine(540+random()*100,151+random()*12,18+random()*23,"#536f70");
        break;
      case 9: // Castle gatehouse and pennants
        rect(421,93,119,48,"#b4a6aa");
        for(const x of [411,466,523]) {
          rect(x,77,24,63,"#a596a1");
          polygon([[x-4,78],[x+12,55],[x+28,78]],"#6f627a");
          rect(x+11,45,2,15,"#5c5462");
          polygon([[x+13,45],[x+26,49],[x+13,52]],"#b96664");
          rect(x+9,88,6,12,"#615d70");
        }
        disc(478,122,10,"#585665"); rect(468,122,20,18,"#585665");
        break;
    }
    return;
  }
  if (theme === 2) {
    for (let i=0;i<100;i++) {
      const x=random()*w,y=random()*100;
      rect(x,y,2,2,"#efdfba");
      if(i%12===0) { rect(x-2,y,6,1,"#efdfba"); rect(x,y-2,1,6,"#efdfba") }
    }
    disc(474,37,23,"#fff0b7"); disc(484,29,22,sky);
    ridge(115,50,"#68749a",46); ridge(133,44,"#414d71",35);
    ridge(158,30,"#222f49",26);
    disc(460,117,20,"#91a0b3"); rect(438,117,44,22,"#bebcae");
    polygon([[455,98],[460,96],[470,117],[465,117]],"#4b5c78");
    rect(438,116,44,4,"#485778"); rect(447,126,6,7,"#ffda8e");
    rect(467,126,6,7,"#ffda8e");
    for(let i=0;i<13;i++) pine(530+random()*115,163,20+random()*48,"#172d38");
  } else {
    disc(465,34,21,theme ? "#ef9c67" : "#fff4b9");
    for(let i=0;i<15;i++) {
      const x=random()*w,y=8+random()*45;
      rect(x,y,12+random()*29,2,"#fffae480");
    }
    if(theme===0) {
      ridge(99,56,"#a7bc90",52); ridge(111,38,"#779c80",37);
      for(let i=0;i<90;i++) pine(random()*w,115,12+random()*24,"#5a846c");
      rect(0,114,w,50,"#a5c4ad");
      for(let i=0;i<95;i++) rect(random()*w,115+random()*49,4+random()*24,1,"#e0ecd093");
      polygon([[280,164],[361,139],[437,138],[497,121],[572,129],[640,104],[640,164]],"#426c52");
      rect(478,82,4,44,"#624d36"); rect(493,82,4,42,"#624d36");
      polygon([[479,89],[482,89],[497,119],[494,119]],"#624d36");
      rect(472,75,30,11,"#a86a43"); rect(475,76,23,5,"#f3cc81");
      rect(484,75,2,7,"#6e5139");
      polygon([[469,75],[486,64],[505,75]],"#384c3c");
      for(let i=0;i<18;i++) pine(530+random()*124,151+random()*23,28+random()*65,"#274e3c");
      pine(344,162,32,"#315e46"); pine(360,162,21,"#315e46");
    } else {
      ridge(101,23,"#b5bda3",65); rect(0,100,w,64,"#78adab");
      for(let i=0;i<150;i++) rect(random()*w,102+random()*62,4+random()*28,2,"#d7e5cc");
      polygon([[413,132],[466,110],[513,108],[541,100],[596,109],[640,91],[640,164],[554,164]],"#777e68");
      polygon([[462,112],[513,101],[539,94],[594,103],[640,85],[640,96],[594,113],[538,103],[513,110]],"#859761");
      polygon([[510,104],[516,54],[530,54],[536,103]],"#fff3d8");
      polygon([[513,81],[514,70],[532,70],[534,81]],"#bd694d");
      rect(514,48,18,8,"#3d5554"); rect(518,48,10,7,"#ffe9a0");
      polygon([[510,48],[523,39],[536,48]],"#9c513e");
      polygon([[350,122],[374,122],[369,128],[354,128]],"#455958");
      polygon([[362,99],[362,120],[350,120]],"#fff4d5");
    }
    for(let i=0;i<3;i++) {
      const x=350+i*17, y=26+i%2*6;
      polygon([[x,y],[x+4,y+1],[x+7,y-1],[x+4,y+3]],"#667967");
    }
  }
}
