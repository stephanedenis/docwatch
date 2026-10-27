
// fabrique une ligne de dossier (fleche + nom + bouton epingle)
function makeDirRow(d, ctx) {
  const wrap = document.createElement('div');
  const el = document.createElement('div');
  el.className = 'dir';
  el.dataset.path = d.path;
  // ctx : arbre elague en cours d'affichage (filtre temporel actif)
  if (ctx) {
    el.dataset.filtre = '1';
    el._fctx = ctx;
    if (d.count != null) el.dataset.count = d.count;
  }
  // compteur de documents retenus, visible seulement en mode filtre
  const compteur = (ctx && d.count != null)
    ? '<span class="cnt">' + d.count + '</span>' : '';
  el.innerHTML = '<span class="arrow">▸</span> 📁 ' +
                 '<span class="label">' + d.name + '</span>' + compteur +
                 '<span class="pin" title="Epingler ce dossier">○</span>';
  if (!ctx && dirHasUnseen(d.path)) el.classList.add('unseen');
  el.onclick = (e) => { e.stopPropagation(); loadDir(el); };
  activerMenuContextuel(el, 'folder', d);
  const pin = el.querySelector('.pin');
  pin.classList.toggle('on', pinnedPaths.has(d.path));
  pin.textContent = pinnedPaths.has(d.path) ? '●' : '○';
  pin.onclick = (e) => {
    e.stopPropagation();
    togglePin(d.path, !pinnedPaths.has(d.path), 'folder');
  };
  const sub = document.createElement('div');
  sub.className = 'children';
  sub.style.display = 'none';
  wrap.appendChild(el);
  wrap.appendChild(sub);
  return wrap;
}

function makeFileRow(f) {
  const el = document.createElement('div');
  el.className = 'file';
  el.dataset.path = f.path;
  el.innerHTML = '📄 ' + f.name +
    '<span class="size">' + Math.round(f.size/1024) + ' Ko</span>' +
    '<span class="pin" title="Epingler ce document">○</span>';
  if (unseen.has(f.path)) el.classList.add('unseen');
  el.onclick = (e) => { e.stopPropagation(); openFile(f.path, el); };
  activerMenuContextuel(el, 'file', f);
  const pin = el.querySelector('.pin');
  const on = pinnedPaths.has(f.path);
  pin.classList.toggle('on', on);
  pin.textContent = on ? '●' : '○';
  pin.onclick = (e) => {
    e.stopPropagation();
    togglePin(f.path, !pinnedPaths.has(f.path), 'file');
  };
  return el;
}

// rend (ou re-rend) le contenu d'un conteneur a partir de ses donnees
function renderBox(box, data, ctx) {
  // les sous-dossiers deja deplies seraient recrees vides : on note leur etat
  // pour le remettre en place apres reconstruction
  const etats = new Map();
  box.querySelectorAll('.children').forEach(sub => {
    const row = sub.previousElementSibling;
    if (row && row.dataset.path) {
      etats.set(row.dataset.path, {
        data: sub._data, loaded: sub.dataset.loaded, affiche: sub.style.display,
      });
    }
  });

  box.innerHTML = '';
  for (const d of sortEntries(data.dirs || [])) box.appendChild(makeDirRow(d, ctx));
  for (const f of sortEntries(data.files || [])) box.appendChild(makeFileRow(f));

  if (etats.size) {
    box.querySelectorAll('.children').forEach(sub => {
      const row = sub.previousElementSibling;
      const etat = row && row.dataset.path ? etats.get(row.dataset.path) : null;
      if (!etat || !etat.loaded) return;
      sub._data = etat.data;
      sub.dataset.loaded = '1';
      sub.style.display = etat.affiche || 'block';
      if (row.querySelector('.arrow')) row.querySelector('.arrow').textContent = '▾';
      renderBox(sub, etat.data, ctx);
    });
  }
  paintUnseen();                       // les nouvelles lignes reprennent leur pastille
}

// --- racine affichee et barre de chemin ---------------------------------
let borne = '';                     // perimetre maximal autorise (racine de depart)

function paintRootbar() {
  const bar = document.getElementById('rootbar');
  if (!bar) return;
  bar.innerHTML = '';
  if (!currentRoot) return;

  // chemin relatif a la borne, chaque segment cliquable
  const rel = (borne && currentRoot.indexOf(borne) === 0)
    ? currentRoot.slice(borne.length).replace(/^[/]/, '') : currentRoot;
  const segments = rel ? rel.split('/') : [];
  let cumul = borne || '';

  const racineBtn = document.createElement('button');
  racineBtn.className = 'crumb';
  racineBtn.textContent = '⌂ ' + ((borne || currentRoot).split('/').pop() || '/');
  racineBtn.title = borne || currentRoot;
  racineBtn.onclick = () => changerRacine(borne || currentRoot);
  bar.appendChild(racineBtn);

  for (const seg of segments) {
    cumul = cumul ? cumul + '/' + seg : seg;
    const sep = document.createElement('span');
    sep.className = 'sep';
    sep.textContent = '›';
    bar.appendChild(sep);
    const b = document.createElement('button');
    b.className = 'crumb';
    b.textContent = seg;
    b.title = cumul;
    b.onclick = () => changerRacine(cumul);
    bar.appendChild(b);
  }

  // remonter d'un cran
  const parent = currentRoot.slice(0, currentRoot.lastIndexOf('/'));
  if (parent && borne && currentRoot !== borne) {
    const up = document.createElement('button');
    up.className = 'crumb up';
    up.textContent = '↑';
    up.title = 'Remonter a ' + parent;
    up.onclick = () => changerRacine(parent);
    bar.appendChild(up);
  }
  // choisir un autre dossier comme racine
  const autre = document.createElement('button');
  autre.className = 'crumb grow';
  autre.textContent = 'changer…';
  autre.title = (borne ? 'Choisir un dossier sous ' + borne : 'Choisir une racine');
  autre.onclick = () => choisirRacine();
  bar.appendChild(autre);
}

async function changerRacine(chemin) {
  try {
    const r = await fetch('/root', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({path: chemin}),
    });
    const data = await r.json();
    if (data.error) { alert('Changement de racine refuse : ' + data.error); return; }
    currentRoot = data.root;
    borne = data.borne || borne;
    // tout ce qui concernait l'ancienne racine devient caduc
    knownMtimes.clear(); sousDirsConnus.clear(); displayedDirs.clear();
    expandedDirs.clear(); unseen.clear(); unseenNames.clear(); unseenMtime.clear();
    vusDirs.clear(); sousDirsIndex = 0;
    lastBodyHash = null;
    await rechargerArbre();
    await rechargerPins();      // la liste depend de la racine affichee
    if (recentActif) await recentCharger();   // le filtre suit la racine
  } catch (e) { /* serveur injoignable */ }
}

// rechargement complet du premier niveau apres un changement de racine
async function rechargerArbre() {
  const tree = document.getElementById('tree');
  tree.innerHTML = '';
  tree._data = null;
  tree.dataset.loaded = '0';
  try {
    const data = await (await fetch('/tree?path=' + encodeURIComponent(currentRoot))).json();
    if (!data || !data.dirs) return;
    loadedAt = data.now || 0;
    trackEntries(data.files);
    rememberMtimes(data.files); rememberMtimes(data.dirs);
    rememberSubdirs(data.dirs);
    tree._data = data;
    renderBox(tree, data);
    tree.dataset.loaded = '1';
    displayedDirs.add(currentRoot);
    for (const d of (data.dirs || [])) displayedDirs.add(d.path);
    paintRootbar();
    paintUnseen();
  } catch (e) {}
}

// choix d'une racine parmi les sous-dossiers du dossier courant
async function choisirRacine() {
  const lignes = [
    'Dossier a afficher comme racine de l’arbre',
    borne ? '(doit rester sous ' + borne + ')' : '',
    '',
    'Chemin courant : ' + currentRoot,
  ];
  const saisie = prompt(lignes.join(String.fromCharCode(10)), currentRoot);
  if (saisie === null) return;
  const chemin = saisie.trim();
  if (!chemin || chemin === currentRoot) return;
  await changerRacine(chemin);
}

async function loadDir(el, vu) {
  const path = el.dataset.path;
  if (vu === undefined) vu = true;     // appel direct = depliage volontaire
  const box = el.nextElementSibling;
  if (box.dataset.loaded === '1') {
    box.style.display = box.style.display === 'none' ? 'block' : 'none';
    el.querySelector('.arrow').textContent = box.style.display === 'none' ? '▸' : '▾';
    return;
  }
  // en mode filtre, le contenu elague est deja connu : on le deplie sans
  // interroger le serveur, ce qui reste coherent avec ce qui est affiche
  if (el._fctx && el._fctx.noeuds) {
    const noeud = el._fctx.noeuds[path];
    if (noeud) {
      box._data = {dirs: noeud.dirs || [], files: noeud.files || []};
      renderBox(box, box._data, el._fctx);
      box.style.display = 'block';
      box.dataset.loaded = '1';
      el.querySelector('.arrow').textContent = '▾';
      return;
    }
  }
  el.querySelector('.arrow').textContent = '⋯';
  const r = await fetch('/tree?path=' + encodeURIComponent(path));
  const data = await r.json();
  box._data = data;                    // memorise pour re-trier sans appel reseau
  if (loadedAt && data.now) {
    trackEntries(data.files);
    rememberMtimes(data.dirs); rememberMtimes(data.files);
    rememberSubdirs(data.dirs);
    // on n'efface le signalement que si c'est l'utilisateur qui deplie :
    // une relecture automatique ne vaut pas consultation
    if (vu) markSeenInDir(path);
  }
  renderBox(box, data);
  box.style.display = 'block';        // un dossier charge doit etre VISIBLE :
                                      // sans cette ligne le contenu reste en
                                      // display:none et il faut recliquer
  box.dataset.loaded = '1';
  displayedDirs.add(path);
  // les sous-dossiers de ce dossier sont visibles a l'ecran : ils peuvent
  // porter le badge d'un changement survenu a l'interieur
  for (const d of (data.dirs || [])) displayedDirs.add(d.path);
  if (vu) expandedDirs.add(path);
  el.querySelector('.arrow').textContent = '▾';
}

// --- epingles -------------------------------------------------------------
let pinnedPaths = new Set();

// --- fichiers modifies et pas encore vus --------------------------------
// Repere les entrees dont la date de modification est posterieure a
// l'ouverture de la page : ce sont celles qui ont change depuis. Elles
// restent signalees tant qu'on ne les a pas ouvertes (fichier) ou depliees
// (dossier).
let loadedAt = 0;            // heure serveur au chargement de la page
let unseen = new Set();      // chemins modifies et non encore vus
let unseenNames = new Map(); // chemin -> nom, pour lister ce qui a change
let unseenMtime = new Map(); // chemin -> date du changement
let knownMtimes = new Map(); // chemin -> mtime, tel que le client l'a affiche
// dossiers reellement consultes par l'utilisateur, et quand : un changement
// anterieur a cette date a deja ete vu, un changement posterieur reste signale
let vusDirs = new Map();

// Modifier un fichier ne change PAS la date de son dossier (verifie sur ce
// systeme) : pour reperer un changement dans un dossier non deplie, il faut
// lire son contenu. On le fait en tache de fond, un sous-dossier a la fois,
// en tourniquet, ce qui evite toute rafale de requetes.
let sousDirsConnus = new Set();
let displayedDirs = new Set();     // dossiers affiches (pour badger le bon niveau)
let expandedDirs = new Set();      // dossiers deplies par l'utilisateur
let sousDirsIndex = 0;

function rememberSubdirs(dirs) {
  for (const d of dirs || []) {
    if (d && d.path) sousDirsConnus.add(d.path);
  }
}

async function explorerSousDirs() {
  if (document.hidden || !loadedAt || !sousDirsConnus.size) return;
  // on ne scrute que les sous-dossiers des dossiers reellement affiches :
  // sans ce filtre, un tour complet de l'arborescence serait trop long pour
  // reperer quoi que ce soit en temps utile
  const liste = Array.from(sousDirsConnus).filter(d => {
    const up = d.slice(0, d.lastIndexOf('/'));
    return expandedDirs.has(up);
  });
  if (!liste.length) return;
  if (sousDirsIndex >= liste.length) sousDirsIndex = 0;   // tour complet
  const chemin = liste[sousDirsIndex++];
  try {
    const data = await (await fetch('/tree?path=' + encodeURIComponent(chemin))).json();
    if (!data || !data.files) return;
    noteServerNow(data.now);
    trackEntries(data.files);
    rememberMtimes(data.files);
    paintUnseen();
  } catch (e) { /* on reprendra au tour suivant */ }
}

function rememberMtimes(entries) {
  for (const e of entries || []) {
    if (e && e.path && e.mtime) knownMtimes.set(e.path, e.mtime);
  }
}

// ne concerne que les fichiers : la date d'un dossier ne reflete pas son
// contenu, on la traite separement en remontant au dossier affiche
function trackEntries(entries) {
  if (!loadedAt) return;
  for (const e of entries || []) {
    if (e && e.mtime && e.mtime > loadedAt) {
      unseen.add(e.path);
      unseenNames.set(e.path, e.name);
      unseenMtime.set(e.path, e.mtime);
    }
  }
}

// interroge le serveur sur tout ce qui est deja affiche : une seule requete
// pour l'ensemble, sans re-telecharger le contenu des dossiers
async function checkKnownFiles() {
  if (!knownMtimes.size) return;
  const known = {};
  knownMtimes.forEach((v, k) => { known[k] = v; });
  try {
    const r = await fetch('/changed', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({known: known}),
    });
    const data = await r.json();
    if (data.error) return;
    noteServerNow(data.now);

    // un fichier modifie est signale lui-meme ; un fichier disparu fait
    // signaler le dossier affiche qui le contenait
    const marquer = (chemin, nom, date) => {
      // un element dont le dossier parent est sous les yeux n'a pas a etre
      // signale s'il a change avant la consultation
      const up = chemin.slice(0, chemin.lastIndexOf('/'));
      if (up && vusDirs.has(up) && date && date < vusDirs.get(up)) return;
      unseen.add(chemin);
      unseenNames.set(chemin, nom);
      if (date) unseenMtime.set(chemin, date);
    };
    // le dossier affiche le plus proche : on s'arrete des qu'on en trouve un,
    // pour signaler « sous » plutot que son parent quand il est visible
    const dossierAffiche = (chemin) => {
      let d = chemin.slice(0, chemin.lastIndexOf('/'));
      while (d && d.length >= currentRoot.length) {
        if (displayedDirs.has(d)) return d;
        d = d.slice(0, d.lastIndexOf('/'));
      }
      return null;
    };

    for (const c of data.changed || []) {
      knownMtimes.set(c.path, c.mtime);
      if (!loadedAt || c.mtime <= loadedAt) continue;
      // on marque le fichier ; le dossier affiche qui le contient est badgé
      // automatiquement par dirHasUnseen, inutile de le marquer aussi
      marquer(c.path, c.name, c.mtime);
    }
    for (const p of data.missing || []) {
      knownMtimes.delete(p);
      const d = dossierAffiche(p);
      if (d) marquer(d, d.slice(d.lastIndexOf('/') + 1), serverNow());
    }
    paintUnseen();
  } catch (e) { /* on retentera au prochain cycle */ }
}

// un dossier deplie vaut consultation de son contenu : on eclaircit ses
// fichiers, sinon ils resteraient signales alors qu'ils sont sous les yeux
function markSeenInDir(dirPath) {
  const prefix = dirPath + '/';
  const maintenant = serverNow();
  vusDirs.set(dirPath, maintenant);
  for (const p of Array.from(unseen)) {
    if (!p.startsWith(prefix)) continue;
    // element directement dans ce dossier, ou sous-dossier immediat : les
    // deux sont sous les yeux une fois le dossier deplie. On n'efface que ce
    // qui est anterieur a cette consultation.
    const reste = p.slice(prefix.length);
    // strictement anterieur : un fichier ecrit dans la meme seconde que la
    // consultation reste signale (granularite des dates a la seconde)
    if (reste && reste.indexOf('/') === -1 &&
        (unseenMtime.get(p) || 1) < maintenant) {
      unseen.delete(p);
      unseenNames.delete(p);
      unseenMtime.delete(p);
    }
  }
  paintUnseen();
}

// horloge du serveur, avancee du temps ecoule depuis le dernier echange :
// les dates du serveur et celles du navigateur ne sont pas comparables
let lastServerNow = 0;
let lastServerAt = 0;
function serverNow() {
  if (!lastServerNow) return Math.floor(Date.now() / 1000);
  return lastServerNow + Math.floor((Date.now() - lastServerAt) / 1000);
}
function noteServerNow(t) {
  if (t) { lastServerNow = t; lastServerAt = Date.now(); }
}

// un dossier merite d'etre signale si lui-meme a change (fichier ajoute ou
// retire) ou si un element deja repere a l'interieur a change
function dirHasUnseen(dirPath) {
  if (unseen.has(dirPath)) return true;
  const prefix = dirPath + '/';
  for (const p of unseen) if (p.startsWith(prefix)) return true;
  return false;
}

function markSeen(path) {
  if (!path) return;
  unseen.delete(path);
  unseenNames.delete(path);
  paintUnseen();
}

function clearUnseen() {
  unseen.clear();
  unseenNames.clear();
  paintUnseen();
}

// met a jour les pastilles de l'arbre et de la barre d'etat
function paintUnseen() {
  document.querySelectorAll('#tree .file').forEach(el => {
    el.classList.toggle('unseen', unseen.has(el.dataset.path));
  });
  document.querySelectorAll('#tree .dir').forEach(el => {
    el.classList.toggle('unseen', dirHasUnseen(el.dataset.path));
  });
  const upd = document.getElementById('upd');
  if (upd && unseen.size) {
    upd.textContent = '↻ ' + unseen.size + ' changement' +
                      (unseen.size > 1 ? 's' : '') + ' non vu' +
                      (unseen.size > 1 ? 's' : '');
    upd.classList.add('on');
  }
}


// --- annonce d'un rafraichissement ----------------------------------------
// Son discret de page tournee, synthetise (aucun fichier a charger).
let audioCtx = null;
let soundOn = true;
try { soundOn = localStorage.getItem('mdserve.sound') !== '0'; } catch (e) {}

function pageTurnSound() {
  if (!soundOn) return;
  try {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    if (!audioCtx) audioCtx = new AC();
    if (audioCtx.state === 'suspended') audioCtx.resume();
    const ctx = audioCtx, now = ctx.currentTime, dur = 0.34;
    // bruit blanc tres court : la matiere premiere du froufrou de papier
    const n = Math.floor(ctx.sampleRate * dur);
    const buf = ctx.createBuffer(1, n, ctx.sampleRate);
    const ch = buf.getChannelData(0);
    for (let i = 0; i < n; i++) ch[i] = (Math.random() * 2 - 1) * 0.5;
    const src = ctx.createBufferSource();
    src.buffer = buf;
    // bande passante haute = papier ; coupure du bas = pas de grondement
    const hp = ctx.createBiquadFilter();
    hp.type = 'highpass'; hp.frequency.value = 900;
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass'; lp.frequency.value = 5200;
    const g = ctx.createGain();
    // enveloppe douce : attaque vive, extinction naturelle
    // crete a 80 % du niveau maximal
    g.gain.setValueAtTime(0.0001, now);
    g.gain.exponentialRampToValueAtTime(0.8, now + 0.03);
    g.gain.exponentialRampToValueAtTime(0.0001, now + dur);
    src.connect(hp); hp.connect(lp); lp.connect(g); g.connect(ctx.destination);
    src.start(now); src.stop(now + dur);
  } catch (e) { /* audio indisponible : on continue sans bruit */ }
}

function blinkBar() {
  const bar = document.getElementById('meta');
  if (!bar) return;
  bar.classList.remove('flash');
  void bar.offsetWidth;              // force le redemarrage de l'animation
  bar.classList.add('flash');
  setTimeout(() => bar.classList.remove('flash'), 1300);
}

function setSoundButton() {
  const b = document.getElementById('sound');
  if (!b) return;
  b.textContent = soundOn ? '🔊' : '🔇';
  b.classList.toggle('off', !soundOn);
  b.title = soundOn
    ? 'Son de rafraichissement : actif (cliquer pour couper)'
    : 'Son de rafraichissement : coupe (cliquer pour activer)';
}

// au chargement : refleter l'etat sans jouer de son
function toggleSoundIfNeeded() {
  setSoundButton();
}

function toggleSound() {
  soundOn = !soundOn;
  try { localStorage.setItem('mdserve.sound', soundOn ? '1' : '0'); } catch (e) {}
  setSoundButton();
  if (soundOn) pageTurnSound();      // retour sonore immediat
}

// --- position de lecture ---------------------------------------------------
// On mesure avec getBoundingClientRect, relatif au viewport : c'est la seule
// grandeur qui reste juste apres un remplacement de contenu, et elle ne
// depend pas d'un offsetTop calcule par le parent.
function topOf(el) {
  const r = el.getBoundingClientRect();
  return r.top + window.scrollY;
}

// On memorise l'element visible le plus haut et son decalage : il sert
// d'ancre pour retrouver la meme phrase apres un re-rendu, meme si le
// document a grandi au-dessus.
function captureAnchor() {
  const main = document.getElementById('main');
  if (!main) return null;
  const children = main.children;
  if (!children.length) return null;
  const top = window.scrollY;
  for (let i = 0; i < children.length; i++) {
    const el = children[i];
    const elTop = topOf(el);
    const bottom = elTop + el.getBoundingClientRect().height;
    if (bottom > top + 2) {
      return { i: i, delta: elTop - top, hash: textHash(el) };
    }
  }
  return null;
}

function textHash(el) {
  const t = (el.textContent || '').slice(0, 220);
  let h = 2166136261;
  for (let i = 0; i < t.length; i++) { h ^= t.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0).toString(36);
}

function restoreAnchor(anchor) {
  if (!anchor) return;
  const main = document.getElementById('main');
  if (!main) return;
  const children = main.children;
  if (!children.length) return;
  // si la mise en page n'est pas encore calculee, toutes les mesures valent 0
  // et restaurer ainsi la lecture sauterait en haut de page : on s'abstient
  // et l'appelant retentera a la frame suivante.
  let measured = 0;
  for (let i = 0; i < children.length; i++) measured += Math.abs(topOf(children[i]));
  if (measured === 0) return false;

  // on cherche d'abord le meme element par son empreinte de texte
  for (let i = 0; i < children.length; i++) {
    if (textHash(children[i]) === anchor.hash) {
      window.scrollTo(0, Math.max(0, topOf(children[i]) - anchor.delta));
      return true;
    }
  }
  // sinon on retombe sur la meme position dans la liste
  if (anchor.i < children.length) {
    window.scrollTo(0, Math.max(0, topOf(children[anchor.i]) - anchor.delta));
    return true;
  }
  return false;
}

// ouvertures volontaires (clic) : on remonte en haut et on n'annonce rien
let suppressAnnounce = false;
// empreinte du contenu actuellement rendu, pour ne signaler que du vrai changement
let lastBodyHash = null;

function bodyHash(html) {
  let h = 2166136261;
  const step = html.length > 4000 ? Math.ceil(html.length / 4000) : 1;
  for (let i = 0; i < html.length; i += step) {
    h ^= html.charCodeAt(i); h = Math.imul(h, 16777619);
  }
  return (h >>> 0).toString(36) + ':' + html.length;
}

// --- en-tete : nom du document + fraicheur --------------------------------
let curPath = null;       // fichier affiche
let curStat = null;       // dernier etat connu (mtime, size, now du serveur)
let curToken = '0';       // jeton de version du fichier rendu
let curDirToken = '0';    // jeton de version du dossier
let curErr = null;        // message d'erreur a conserver (fichier disparu...)
let lastMs = 0;           // duree du dernier rendu
let lastCache = false;
let inFlight = false;

function two(n) { return String(n).padStart(2, '0'); }

function absDate(sec) {
  if (!sec) return '';
  const d = new Date(sec * 1000);
  return two(d.getDate()) + '/' + two(d.getMonth() + 1) + '/' + d.getFullYear() +
         ' ' + two(d.getHours()) + ':' + two(d.getMinutes()) + ':' + two(d.getSeconds());
}

// age en secondes, rendu lisible ; >= 1 h on passe en heures/jours
function relDate(sec) {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - sec));
  if (s < 60) return s + ' s';
  if (s < 3600) return Math.floor(s / 60) + ' min';
  if (s < 86400) return Math.floor(s / 3600) + ' h';
  return Math.floor(s / 86400) + ' j';
}

// age exact en secondes, separe par des espaces fines (usage francais)
function secondsExact(sec) {
  const s = Math.max(0, Math.floor(Date.now() / 1000 - sec));
  return s.toLocaleString('fr-FR') + ' s';
}

function paintHeader() {
  const fname = document.getElementById('fname');
  if (!fname) return;
  if (!curPath) {
    // ne pas effacer le message d'erreur deja pose (fichier supprime, 404...)
    if (!curErr) {
      fname.textContent = '—';
      document.getElementById('fmeta').textContent = '';
      document.getElementById('frel').textContent = '';
    }
    return;
  }
  curErr = null;
  fname.textContent = curStat && curStat.name ? curStat.name : curPath;
  fname.title = curPath;
  const st = curStat || {};
  document.getElementById('fmeta').textContent =
    (st.size != null ? (st.size / 1024).toFixed(1) + ' Ko' : '') +
    (lastMs ? '  ·  rendu ' + lastMs + ' ms' + (lastCache ? ' (cache)' : '') : '');
  let rel = st.mtime ? 'modifie il y a ' + relDate(st.mtime) +
                       '  (' + absDate(st.mtime) + '  =  ' +
                       secondsExact(st.mtime) + ')' : '';
  if (st.dir_mtime) {
    rel += '   ·   dossier ' + (st.dir_name || '') +
           ' il y a ' + relDate(st.dir_mtime);
  }
  document.getElementById('frel').textContent = rel;
  document.getElementById('frel').title =
    'Age exact en secondes, fuseau : ' +
    Intl.DateTimeFormat().resolvedOptions().timeZone;
}

// rafraichit l'age affiche (vieillit tout seul, sans appel reseau)
setInterval(paintHeader, 1000);

// --- rafraichissement temps reel ------------------------------------------
// Interrogation legere de /stat : le serveur compare les jetons et repond
// seulement si quelque chose a change.
async function pollOnce() {
  if (!curPath || inFlight || document.hidden) return;
  inFlight = true;
  try {
    const u = '/stat?path=' + encodeURIComponent(curPath) +
              '&token=' + encodeURIComponent(curToken) +
              '&dir_token=' + encodeURIComponent(curDirToken);
    const r = await fetch(u);
    if (r.status === 404) {
      // le fichier a disparu : on le dit clairement, et on arrete de sonder
      curPath = null;
      curErr = 'fichier supprime ou deplace — contenu fige';
      const el = document.getElementById('frel');
      if (el) {
        el.textContent = curErr;
        el.title = 'le fichier n’existe plus sur le disque';
      }
      return;
    }
    const st = await r.json();
    if (st.error || !st.exists) return;
    curStat = st;
    if (st.changed) {
      // reecrire un fichier modifie aussi son dossier : inutile de recharger
      // l'arbre en plus, le nouveau dir_token sera repris par openFile
      await openFile(curPath, null, true);
    } else if (st.dir_changed) {
      await refreshLoadedDirs();             // un fichier a ete ajoute ou retire
    }
    paintHeader();
  } catch (e) {
    /* serveur injoignable : on retentera au prochain cycle */
  } finally {
    inFlight = false;
  }
}
// deux boucles independantes : le document ouvert d'un cote, la recherche
// de changements dans tout ce qui est affiche de l'autre (elle doit tourner
// meme si aucun document n'est ouvert)
setInterval(pollOnce, 3000);
setInterval(() => {
  if (document.hidden || !loadedAt || !knownMtimes.size) return;
  checkKnownFiles();
}, 3000);
// une lecture complete des dossiers affiches est necessaire pour reperer les
// fichiers AJOUTES : `/changed` ne connait que les chemins deja vus. On
// espace ce cycle, plus couteux qu'un simple stat.
setInterval(() => {
  if (document.hidden || !loadedAt) return;
  refreshLoadedDirs();
  if (recentActif) recentCharger();
}, 15000);
// contenu des sous-dossiers affiches, un par cycle (tourniquet)
setInterval(explorerSousDirs, 2000);

document.addEventListener('visibilitychange', () => {
  if (!document.hidden) pollOnce();     // retour sur l'onglet : controle immediat
});

// relit les dossiers deja ouverts et met a jour les lignes qui ont change
async function refreshLoadedDirs() {
  // En mode filtre, les dossiers affiches viennent de l'arbre ELAGUE : les
  // recharger depuis /tree remettrait le contenu complet et ferait basculer
  // l'affichage entre arbre filtre et arbre entier. C'est recentCharger() qui
  // entretient l'arbre elague.
  if (recentActif) { refreshPins(); paintUnseen(); return; }
  const boxes = Array.from(document.querySelectorAll('#tree .children, #tree'))
    .filter(b => b.dataset.loaded === '1' && b._data);
  for (const box of boxes) {
    const row = box.previousElementSibling;
    const path = (box.id === 'tree') ? currentRoot : (row && row.dataset.path);
    if (!path) continue;
    try {
      const data = await (await fetch('/tree?path=' + encodeURIComponent(path))).json();
      if (!data || !data.dirs) continue;
      trackEntries(data.files);
      rememberMtimes(data.dirs); rememberMtimes(data.files);
      rememberSubdirs(data.dirs);
      const before = JSON.stringify([box._data.dirs, box._data.files]);
      const after = JSON.stringify([data.dirs, data.files]);
      if (before !== after) {
        box._data = data;
        renderBox(box, data);
      }
    } catch (e) { /* on ignore ce cycle */ }
  }
  refreshPins();
  paintUnseen();
}

async function refreshPins() {
  try {
    const r = await fetch('/pins');
    const data = await r.json();
    if (data && data.pins) renderPins(data.pins);
  } catch (e) {}
}

// apres un changement de racine : on re-elague et on recharge la liste
async function rechargerPins() {
  await loadPins(true);
}

async function refreshAll() {
  if (recentActif) { await recentCharger(true); }
  await refreshLoadedDirs();
  if (curPath) await openFile(curPath, null, true);
}

let currentRoot = '';
let currentFile = null;

// --- tri ------------------------------------------------------------------
// 'date' = plus recent d'abord (defaut) ; 'nom' = alphabetique.
let sortMode = 'date';
try {
  const saved = localStorage.getItem('mdserve.sort');
  if (saved === 'date' || saved === 'nom') sortMode = saved;
} catch (e) { /* localStorage indisponible : on garde le defaut */ }

function cmpEntries(a, b) {
  if (sortMode === 'nom') return a.name.localeCompare(b.name, 'fr');
  const d = (b.mtime || 0) - (a.mtime || 0);
  return d !== 0 ? d : a.name.localeCompare(b.name, 'fr');
}

function sortEntries(list) {
  return [...list].sort(cmpEntries);
}

function setSort(mode) {
  if (mode !== 'date' && mode !== 'nom') return;
  sortMode = mode;
  try { localStorage.setItem('mdserve.sort', mode); } catch (e) {}
  document.querySelectorAll('#sortbar button').forEach(b => {
    b.classList.toggle('on', b.dataset.mode === mode);
  });
  const lbl = document.getElementById('sortlabel');
  if (lbl) lbl.textContent = mode === 'date' ? 'plus recents' : 'alphabetique';
  reorder();
}

// reaffiche arbre et epingles depuis les donnees deja chargees (aucun appel reseau)
function reorder() {
  document.querySelectorAll('#tree .children, #tree').forEach(box => {
    if (box.dataset.loaded !== '1' || !box._data) return;
    renderBox(box, box._data);
  });
  if (window._pinsCache) renderPins(window._pinsCache);
}

async function loadPins(prune) {
  try {
    const r = await fetch('/pins' + (prune ? '?prune=1' : ''));
    const data = await r.json();
    signalerRetires(data.retires);
    renderPins(data.pins || {folders: [], files: []});
  } catch (e) { /* serveur indisponible : on n'affiche rien */ }
}

// les epingles disparues sont retirees du stockage : on le dit une fois,
// discretement, pour que la disparition ne soit pas mysterieuse
function signalerRetires(retires) {
  if (!retires || !retires.length) return;
  const el = document.getElementById('upd');
  if (!el) return;
  const noms = retires.map(r => r.name).join(', ');
  el.textContent = '☆ ' + retires.length + ' epingle' +
                   (retires.length > 1 ? 's' : '') + ' retiree' +
                   (retires.length > 1 ? 's' : '') + ' (disparue' +
                   (retires.length > 1 ? 's' : '') + ') : ' + noms;
  el.classList.add('on');
  el.title = retires.map(r => r.path).join('\n');
  clearTimeout(window._retiresTimer);
  window._retiresTimer = setTimeout(() => el.classList.remove('on'), 6000);
}

function renderPins(pins) {
  if (Array.isArray(pins)) pins = {folders: pins, files: []};
  window._pinsCache = pins;            // conserve pour re-trier sans appel reseau
  const dossiers = pins.folders || [];
  const fichiers = pins.files || [];
  pinnedPaths = new Set(dossiers.concat(fichiers).map(p => p.path));

  const box = document.getElementById('pins');
  let h = '<h3>📌 Epingles</h3>';
  if (!dossiers.length && !fichiers.length) {
    h += '<div class="empty">Survolez un dossier ou un document, ' +
         'cliquez ○ pour l’epingler.</div>';
  }
  box.innerHTML = h;

  const ligne = (p, estFichier, sousParent) => {
    const el = document.createElement('div');
    el.className = 'pinned' + (estFichier ? ' estfile' : '') + (sousParent ? ' sous' : '');
    el.title = p.path;
    el.innerHTML = (estFichier ? '📄 ' : '📁 ') +
                   '<span class="pname">' + (p.name || p.path) + '</span>' +
                   '<span class="pout" title="Retirer des epingles">✕</span>';
    // un document s'ouvre dans le lecteur, un dossier se deplie dans l'arbre
    el.onclick = estFichier
      ? () => openFile(p.path, null)
      : () => expandHighlight(p.path);
    el.querySelector('.pout').onclick = (e) => {
      e.stopPropagation();
      togglePin(p.path, null, estFichier ? 'file' : 'folder');
    };
    box.appendChild(el);
  };

  // un document epingle se range sous le dossier epingle qui le contient
  const pris = new Set();
  for (const d of dossiers) {
    ligne(d, false, false);
    const prefixe = d.path + '/';
    const enfants = fichiers.filter(f => f.path.startsWith(prefixe));
    for (const f of enfants) { ligne(f, true, true); pris.add(f.path); }
  }
  for (const f of fichiers) if (!pris.has(f.path)) ligne(f, true, false);

  // met a jour les pastilles de l'arbre et le bouton du document affiche
  document.querySelectorAll('#tree .dir, #tree .file').forEach(el => {
    const b = el.querySelector('.pin');
    if (b) b.classList.toggle('on', pinnedPaths.has(el.dataset.path));
  });
  majBoutonEpingler();
}

// le bouton de la barre d'etat reflete l'etat du document affiche
function majBoutonEpingler() {
  const b = document.getElementById('pinfile');
  if (!b) return;
  const on = !!(curPath && pinnedPaths.has(curPath));
  b.textContent = on ? '★' : '☆';
  b.classList.toggle('on', on);
  b.title = on ? 'Retirer ce document des epingles'
               : 'Epingler le document affiche';
}

async function togglePin(path, on, kind) {
  if (!path) return;
  const dejaLa = pinnedPaths.has(path);
  const action = (on === true) ? 'add' : (on === false) ? 'remove'
               : (dejaLa ? 'remove' : 'add');
  const r = await fetch('/pins', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: action, path: path, kind: kind || 'folder'}),
  });
  const data = await r.json();
  if (data.error) { alert('Epinglage refuse : ' + data.error); return; }
  renderPins(data.pins || {folders: [], files: []});
}

// deplie l'arbre jusqu'au dossier demande, puis le met en evidence
function findDirEl(path) {
  return Array.from(document.querySelectorAll('.dir'))
              .find(el => el.dataset.path === path) || null;
}

async function ensureLoaded(row) {
  const box = row.nextElementSibling;
  if (box.dataset.loaded !== '1') await loadDir(row);
  return row.nextElementSibling;
}

// --- filtre temporel : documents modifies recemment ---------------------
let recentActif = false;
let recentHeures = 24;
let recentTimer = null;

function relDepuis(sec) {
  const s = Math.max(0, Math.floor(serverNow() - sec));
  if (s < 60) return 'il y a ' + s + ' s';
  if (s < 3600) return 'il y a ' + Math.floor(s / 60) + ' min';
  if (s < 86400) return 'il y a ' + Math.floor(s / 3600) + ' h';
  return 'il y a ' + Math.floor(s / 86400) + ' j';
}

// bouton rapide : 1 h, 24 h, 7 j
function recentRapide(h) {
  recentHeures = h;
  const champ = document.getElementById('fheures');
  if (champ) champ.value = h;
  majBoutonsFiltre();
  recentLancer();
}

function majBoutonsFiltre() {
  document.querySelectorAll('#filtrebar button[data-h]').forEach(b => {
    b.classList.toggle('on', recentActif && Number(b.dataset.h) === recentHeures);
  });
  const tout = document.getElementById('ftout');
  if (tout) tout.classList.toggle('on', !recentActif);
}

async function recentLancer() {
  const champ = document.getElementById('fheures');
  const v = champ ? parseFloat(champ.value) : recentHeures;
  recentHeures = (isFinite(v) && v > 0) ? Math.min(v, 8760) : 24;
  if (champ) champ.value = recentHeures;
  recentActif = true;
  majBoutonsFiltre();
  const arbre = document.getElementById('tree');
  // l'arbre reste en place : il est simplement elague au contenu filtre
  arbre.dataset.loaded = '0';
  arbre.innerHTML = '<div class="hint">Recherche des documents modifies ' +
                    'depuis ' + recentHeures + ' h…</div>';
  await recentCharger();
}

function recentArreter() {
  recentActif = false;
  window._recentCtx = null;
  majBoutonsFiltre();
  const info = document.getElementById('filtreinfo');
  if (info) info.textContent = '';
  // l'arbre complet doit etre reconstruit : le precedent etait elague
  const arbre = document.getElementById('tree');
  arbre.innerHTML = '';
  arbre._data = null;
  arbre._ctx = null;
  arbre.dataset.loaded = '0';
  rechargerArbre();
}

async function recentCharger(force) {
  try {
    const r = await fetch('/recent?heures=' + encodeURIComponent(recentHeures) +
                          (force ? '&force=1' : ''));
    const d = await r.json();
    if (d.error) return;
    noteServerNow(d.maintenant);
    renderRecent(d);
  } catch (e) { /* on retentera */ }
}

// une arborescence affichee vaut consultation de ce qu'elle montre
function markSeenDansArbre(noeud) {
  const prefixe = noeud.path + '/';
  for (const p of Array.from(unseen)) {
    if (!p.startsWith(prefixe)) continue;
    const reste = p.slice(prefixe.length);
    if (reste && reste.indexOf('/') === -1 && unseenMtime.get(p) <= serverNow()) {
      unseen.delete(p); unseenNames.delete(p); unseenMtime.delete(p);
    }
  }
  vusDirs.set(noeud.path, serverNow());
  for (const x of (noeud.dirs || [])) markSeenDansArbre(x);
}

// serialise un arbre en ignorant les horodatages d'enveloppe : seuls le
// contenu et les dates des elements comptent pour detecter un changement
function contenuStable(noeud) {
  return JSON.stringify(noeud, (cle, val) => cle === 'maintenant' ? undefined : val);
}

function renderRecent(d) {
  const info = document.getElementById('filtreinfo');
  const arbre = document.getElementById('tree');
  if (!arbre) return;
  const a = d.arbre;
  if (!a || !a.total) {
    arbre.innerHTML = '<div class="hint">Aucun document modifie depuis ' +
                      recentHeures + ' h.</div>';
    arbre.dataset.loaded = '1';
    if (info) info.textContent = 'Aucun document modifie depuis ' + recentHeures + ' h';
    return;
  }

  // l'arbre elague est affiche : on enregistre ses dates pour que la
  // detection de changement continue de fonctionner, et on marque comme vus
  // les documents qu'il montre (l'utilisateur les a sous les yeux)
  for (const e of (d.elements || [])) rememberMtimes([e]);
  markSeenDansArbre(a);

  // On ne reconstruit QUE si les donnees ont change. Sans ce garde-fou, le
  // cycle de rafraichissement de 15 s reconstruisait tout l'arbre a
  // l'identique : les dossiers se repliaient, ce qui donnait l'impression
  // que l'arbre basculait et clignotait.
  // `maintenant` change a chaque reponse : l'inclure ferait croire a un
  // changement de contenu et relancerait une reconstruction inutile
  const signature = contenuStable(a) + '|' + currentRoot;
  const precedent = window._recentSignature || null;

  if (precedent !== signature) {
    // index des noeuds elagues : permet de deplier sans revenir au serveur
    const noeuds = {};
    (function indexer(n) {
      noeuds[n.path] = n;
      for (const x of (n.dirs || [])) indexer(x);
    })(a);
    const ctx = {noeuds: noeuds};
    window._recentCtx = ctx;
    window._recentSignature = signature;

    // on note ce qui etait deplie et ou l'on etait, pour le remettre apres
    const ouverts = [];
    arbre.querySelectorAll('.dir').forEach(r => {
      const b = r.nextElementSibling;
      if (b && b.dataset.loaded === '1' && b.style.display !== 'none') ouverts.push(r.dataset.path);
    });
    const defilement = document.getElementById('side').scrollTop;

    arbre.innerHTML = '';
    arbre._data = {dirs: a.dirs || [], files: a.files || []};
    arbre._ctx = ctx;
    renderBox(arbre, arbre._data, ctx);
    arbre.dataset.loaded = '1';

    // redeploiement progressif, une frame par niveau, sans refaire clignoter
    (async () => {
      for (const chemin of ouverts) {
        const r = findDirEl(chemin);
        if (r && r.nextElementSibling && r.nextElementSibling.dataset.loaded !== '1') {
          await loadDir(r, false);
          await new Promise(res => requestAnimationFrame(res));
        }
      }
      const side = document.getElementById('side');
      if (side && defilement) side.scrollTop = defilement;
    })();
  }
  paintUnseen();

  if (info) {
    const h = recentHeures >= 48 ? (recentHeures / 24) + ' j' : recentHeures + ' h';
    info.textContent = a.total + ' document' + (a.total > 1 ? 's' : '') +
      ' modifie' + (a.total > 1 ? 's' : '') + ' depuis ' + h +
      '  ·  arbre elague' +
      (d.tronque ? '  ·  parcours partiel (arbre tres grand)' : '');
  }
}

// --- menu contextuel de l'arbre ----------------------------------------
// Clic droit sur un dossier : le definir comme racine, l'epingler, le
// deplier. Clic droit sur un document : l'ouvrir, l'epingler.
function fermerMenu() {
  const m = document.getElementById('ctx');
  if (m) m.hidden = true;
}

function ouvrirMenu(x, y, titre, entrees) {
  const m = document.getElementById('ctx');
  if (!m) return;
  m.innerHTML = '';
  const t = document.createElement('div');
  t.className = 'titre';
  t.textContent = titre;
  t.title = titre;
  m.appendChild(t);
  for (const e of entrees) {
    if (!e) continue;
    const it = document.createElement('div');
    it.className = 'item' + (e.actif === false ? ' desactive' : '');
    it.textContent = e.label;
    if (e.fn && e.actif !== false) it.onclick = () => { fermerMenu(); e.fn(); };
    m.appendChild(it);
  }
  // on affiche hors ecran d'abord pour connaitre la taille reelle
  m.hidden = false;
  m.style.left = '0px';
  m.style.top = '0px';
  const r = m.getBoundingClientRect();
  const vw = window.innerWidth || 1200, vh = window.innerHeight || 800;
  m.style.left = Math.max(4, Math.min(x, vw - r.width - 6)) + 'px';
  m.style.top = Math.max(4, Math.min(y, vh - r.height - 6)) + 'px';
}

// un dossier est considere deplie des que son contenu est charge : la
// restauration d'etat peut remplir un conteneur encore masque, donc on ne
// se fie pas a la visibilite mais au chargement
function dejaDeplie(chemin) {
  const row = findDirEl(chemin);
  if (!row) return false;
  const box = row.nextElementSibling;
  return !!(box && box.dataset.loaded === '1');
}

function menuDossier(d) {
  const estRacine = (d.path === currentRoot);
  const zoneRacine = (d.path === borne);
  const epingle = pinnedPaths.has(d.path);
  return [
    { label: '⤴  Afficher ce dossier comme racine', actif: !estRacine,
      fn: () => changerRacine(d.path) },
    { label: '⌂  Revenir a la racine de depart', actif: !zoneRacine,
      fn: () => changerRacine(borne) },
    null,
    { label: epingle ? '★  Retirer des epingles' : '☆  Epingler ce dossier',
      fn: () => togglePin(d.path, !epingle, 'folder') },
    { label: dejaDeplie(d.path) ? '▾  Replier ce dossier' : '▸  Deplier ce dossier',
      fn: () => { const r = findDirEl(d.path); if (r) loadDir(r); } },
  ];
}

function menuFichier(f) {
  const epingle = pinnedPaths.has(f.path);
  return [
    { label: '▶  Ouvrir dans le lecteur', fn: () => openFile(f.path, null) },
    null,
    { label: epingle ? '★  Retirer des epingles' : '☆  Epingler ce document',
      fn: () => togglePin(f.path, !epingle, 'file') },
  ];
}

function activerMenuContextuel(el, kind, data) {
  el.addEventListener('contextmenu', (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    // on ne deplie pas d'office : le menu propose de le faire
    ouvrirMenu(ev.clientX || 40, ev.clientY || 40, data.name,
               kind === 'folder' ? menuDossier(data) : menuFichier(data));
  });
}

// fermeture : clic ailleurs, Echap, defilement, redimensionnement
document.addEventListener('click', (e) => {
  const m = document.getElementById('ctx');
  if (m && !m.hidden && !m.contains(e.target)) fermerMenu();
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') fermerMenu(); });
window.addEventListener('resize', fermerMenu);
window.addEventListener('scroll', fermerMenu, true);

// deplie l'arbre jusqu'au dossier vise et le met en evidence
async function expandHighlight(target) {
  await expandTo(target);
  const row = findDirEl(target);
  if (row) {
    row.scrollIntoView({block:'center'});
    row.style.transition = 'background .35s';
    row.style.background = '#4a9eff44';
    setTimeout(() => { row.style.background = ''; }, 1400);
  }
}

async function expandTo(target) {
  const chain = [];
  let cur = target;
  while (cur.length > currentRoot.length) {
    chain.unshift(cur);
    const up = cur.lastIndexOf('/');
    if (up <= 0) break;
    cur = cur.slice(0, up);
  }
  for (const p of chain) {
    const row = findDirEl(p);
    if (!row) return;                 // ce niveau n'est pas affiche : on s'arrete
    const box = await ensureLoaded(row);
    const isTarget = (p === target);
    if (isTarget) {
      row.scrollIntoView({block:'center'});
      row.style.transition = 'background .35s';
      row.style.background = '#4a9eff44';
      setTimeout(() => { row.style.background = ''; }, 1400);
      return;
    }
    if (!box.isConnected) return;
  }
}

// silent=true : rafraichissement en tache de fond, sans vider l'ecran
async function openFile(path, el, silent) {
  document.querySelectorAll('.file.active').forEach(x => x.classList.remove('active'));
  if (el) el.classList.add('active');
  currentFile = path;
  curPath = path;
  markSeen(path);              // ce fichier est desormais consulte
  // avant de remplacer le contenu : memoriser ou en est la lecture
  const anchor = silent ? captureAnchor() : null;
  if (!silent) {
    document.getElementById('main').innerHTML =
      '<p class="hint">Rendu en cours…</p>';
  }
  const t0 = performance.now();
  // force=1 : le fichier vient de changer, on veut la derniere version
  const url = '/render?path=' + encodeURIComponent(path) + (silent ? '&force=1' : '');
  const r = await fetch(url);
  if (r.status === 404) {
    curPath = null;
    curErr = 'fichier absent';
    document.getElementById('main').innerHTML =
      '<p class="hint">Ce fichier n’existe plus : ' + path + '</p>';
    document.getElementById('frel').textContent = curErr;
    return;
  }
  const data = await r.json();
  if (data.error) {
    if (!silent) document.getElementById('main').innerHTML =
      '<p class="hint">Erreur : ' + data.error + '</p>';
    return;
  }
  // le contenu a-t-il reellement change ? (le mtime peut bouger sans
  // modification visible, un simple « touch » par exemple)
  const newHash = bodyHash(data.body || '');
  const reallyChanged = lastBodyHash !== null && newHash !== lastBodyHash;
  lastBodyHash = newHash;

  if (!silent) window.scrollTo(0, 0);
  document.getElementById('main').innerHTML = data.body;
  // memorise les jetons de version : ce sont eux que le serveur comparera
  curToken = data.token != null ? String(data.token) : '0';
  curDirToken = data.dir_token != null ? String(data.dir_token) : '0';
  curStat = data;
  lastMs = data.ms || 0;
  lastCache = !!data.cache;
  document.title = (data.name || path.split('/').pop());
  paintHeader();
  majBoutonEpingler();

  if (silent) {
    // signaler seulement si le texte affiche a bouge
    if (reallyChanged) {
      blinkBar();
      pageTurnSound();
    }
    // restaurer la lecture des que la mise en page est disponible ; on
    // retente quelques frames au cas ou le navigateur ne l'a pas encore
    // calculee (mesures a 0).
    const sel = anchor;
    const nextFrame = window.requestAnimationFrame
      ? window.requestAnimationFrame.bind(window)
      : (fn) => setTimeout(fn, 16);
    let essais = 0;
    const tryRestore = () => {
      if (restoreAnchor(sel) === false && ++essais < 12) nextFrame(tryRestore);
    };
    nextFrame(tryRestore);
  }
}
