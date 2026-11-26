// Config: a rail with one button per catalog group, always visible, and a panel beside it with the cards of the
// group being configured. The panel is closed until a rail button is clicked.
import { GROUPS, item, fits } from '../data/catalog';
import { Ico } from './icons';
import { useI18n } from '../i18n';

interface Props {
  selection: Record<string, string>;
  active: string;                      // the group in focus, or 'overall'
  open: boolean;                       // the cards of the active group are shown
  onPick: (g: string) => void;         // a rail button: focus that group and open its cards (again = close)
  onClose: () => void;
  onSelect: (g: string, id: string) => void;
}

export function LeftPanel(p: Props) {
  const { t, tx } = useI18n();
  const g = p.open ? GROUPS.find((x) => x.id === p.active) : undefined;
  return (
    <>
      <nav className="rail float" aria-label={t('configure')}>
        {GROUPS.map((x) => {
          const it = item(x.id, p.selection[x.id]);
          return (
            <button key={x.id} className={'rail-btn' + (p.active === x.id ? ' on' : '')} aria-expanded={g?.id === x.id}
              title={`${tx(x.title)}: ${it ? tx(it.name) : t('none')}`} onClick={() => p.onPick(x.id)}>
              {it && <Ico name={it.icon} size={24} />}<span>{tx(x.title)}</span>
            </button>
          );
        })}
      </nav>
      {g && (
        <aside className="left float">
          <div className="left-head">
            <h2 title={tx(g.hint)}>{tx(g.title)}</h2>
            <button className="icon-btn" title={t('closePanel')} aria-label={t('closePanel')} onClick={p.onClose}><Ico name="close" size={18} /></button>
          </div>
          <div className="cards">
            {g.items.map((it) => {
              // an adapter made for another carrier cannot be picked
              const unfit = g.id === 'adapter' && !it.disabled && !fits(it, p.selection.carrier);
              const why = it.disabled ? t('planned') : unfit ? t('notForCarrier') : '';
              return (
                <button key={it.id} disabled={it.disabled || unfit} title={why ? `${tx(it.name)} (${why})` : `${tx(it.name)}${it.subtitle ? ' · ' + tx(it.subtitle) : ''}`}
                  className={'card' + (p.selection[g.id] === it.id ? ' selected' : '')}
                  onClick={() => p.onSelect(g.id, it.id)}>
                  <Ico name={it.icon} size={32} />
                  <span className="card-name">{tx(it.name)}</span>
                  {why && <span className="card-sub">{why}</span>}
                </button>
              );
            })}
          </div>
        </aside>
      )}
    </>
  );
}
