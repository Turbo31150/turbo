// Fonctions utilitaires partagees — canvas/utils.js

// Strip <think> tags (closed + unclosed/truncated by max_tokens)
function stripThink(text) {
  if (!text) return '';
  return text.replace(/<think>[\s\S]*?<\/think>/gi, '').replace(/<think>[\s\S]*$/gi, '').replace(/^\/no_?think\s*/i, '').trim();
}

// Triggers et profils pour enhanceQuery
const COT_TRIGGERS = ['pourquoi','explique','compare','analyse','difference','comment','quel est','quelle est','avantage','inconvenient','trade-off','meilleur','debug','erreur','bug','fix','probleme','optimise','ameliore','refactor','calcul','combien','probabilite','raisonne','logique','dedui','prouve','demontre','cause','consequence'];
const CODE_TRIGGERS = ['code','script','fonction','classe','api','implementation','programme','ecris','cree','python','javascript','typescript','bash','powershell','sql','html','css','react','node','express','fastapi','django'];
const STRUCT_TRIGGERS = ['liste','enumere','resume','synthese','tableau','etapes','plan','checklist','compare','vs','difference','recapitule','inventaire'];
const COT_CATS = new Set(['raison','math','ia','archi','sec','code']);
const CODE_CATS = new Set(['code','auto','system']);

const MODEL_PROFILES = {
  M1:  { strengths: 'rapide, polyvalent, bon raisonnement', weaknesses: 'contexte court, peut divaguer', style: 'concis, structure avec markdown, listes a puces, blocs de code' },
  M2:  { strengths: 'reasoning deepseek-r1, bon raisonnement, ctx 27k', weaknesses: '8.5s latence', style: 'raisonnement etape par etape, code complet, pensee profonde' },
  M3:  { strengths: 'reasoning deepseek-r1, ctx 25k, 1 GPU dedie', weaknesses: '18s latence, 1 GPU only', style: 'raisonnement etape par etape, analyse methodique' },
  OL1: { strengths: 'ultra-rapide, bon pour triage', weaknesses: 'superficiel sur questions complexes', style: 'reponses directes, listes, pas de verbiage' }
};

function enhanceQuery(text, cat, nodeId) {
  const low = text.toLowerCase();
  const hints = [];

  if (COT_CATS.has(cat) && COT_TRIGGERS.some(t => low.includes(t)))
    hints.push('METHODE: Raisonne etape par etape. Numerate chaque etape. Verifie ta conclusion.');

  if (CODE_CATS.has(cat) && CODE_TRIGGERS.some(t => low.includes(t)))
    hints.push('CODE: Complet, fonctionnel, avec imports. Commente les parties non-evidentes. Gere les erreurs.');

  if (STRUCT_TRIGGERS.some(t => low.includes(t)))
    hints.push('FORMAT: Structure avec ## titres, - listes, **gras** pour les points cles.');

  if (cat === 'math' || cat === 'raison')
    hints.push('VERIFICATION: Apres ta reponse, relis-la et corrige toute erreur AVANT de conclure.');

  if (cat === 'sec' || cat === 'trading' || cat === 'web')
    hints.push('PRECISION: Si tu n\'es pas certain d\'un fait, dis-le explicitement. Jamais d\'invention.');

  const profile = MODEL_PROFILES[nodeId];
  if (profile) {
    hints.push('STYLE: ' + profile.style);
  }

  if (nodeId === 'OL1' || nodeId === 'M3')
    hints.push('IMPORTANT: Sois CONCIS. Va droit au but. Max 3-5 points cles.');

  if (!hints.length) return text;
  return text + '\n\n[' + hints.join(' | ') + ']';
}

function postProcessResponse(text, cat) {
  if (!text) return text;
  let out = text;

  out = out.replace(/<think>[\s\S]*?<\/think>/gi, '');
  out = out.replace(/<think>[\s\S]*$/gi, '');
  out = out.replace(/^\/no_?think\s*/i, '');
  out = out.replace(/^(As an AI|En tant qu'IA|Je suis un modele|I am a language model)[^\n]*\n?/gim, '');
  out = out.replace(/\n{4,}/g, '\n\n\n');

  const lines = out.trimEnd().split('\n');
  const last = lines[lines.length - 1];
  if (last && last.length > 20 && !last.match(/[.!?\)\]\}»"']$/)) {
    if (last.match(/\b(et|mais|car|donc|or|ni|que|qui|dont|ou|pour|avec|dans|sur|par|de|du|des|le|la|les|un|une)\s*$/i)) {
      lines.pop();
    }
  }
  out = lines.join('\n').trim();

  return out;
}

module.exports = {
  stripThink,
  enhanceQuery,
  postProcessResponse,
  COT_TRIGGERS,
  CODE_TRIGGERS,
  STRUCT_TRIGGERS,
  COT_CATS,
  CODE_CATS,
  MODEL_PROFILES
};
