// Config: a rail with one button per catalog group, always visible, and a panel beside it with the cards of the
// group being configured. The panel is closed until a rail button is clicked.
import { Fragment } from 'react';
import { GROUPS, item, fits, variantOf } from '../data/catalog';
import { Ico } from './icons';
import { useI18n } from '../i18n';

interface Props {
  selection: Record<string, string>;
  active: string;                      // the group in focus, or 'overall'
  open: boolean;                       // the cards of the active group are shown
  onPick: (g: string) => void;         // a rail button: focus that group and open its cards (again = close)
  onClose: () => void;
  onSelect: (g: string, id: string) => void;
  onVariant: (g: string, key: string, id: string) => void;   // the switch under a selected card
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
            {g.items.map((it, i) => {
              // an adapter made for another carrier, or a tip made for another pusher, cannot be picked
              const unfit = !it.disabled && ((g.id === 'adapter' && !fits(it, p.selection.carrier)) || (g.id === 'tip' && !fits(it, p.selection.pusher)));
              const why = it.disabled ? t('planned') : unfit ? t(g.id === 'tip' ? 'notForPusher' : 'notForCarrier') : '';
              const selected = p.selection[g.id] === it.id;
              const v = selected && it.variant ? it.variant : undefined;
              const choice = v ? variantOf(g.id, it, p.selection) : undefined;
              // a divider where a new section starts (sections are given in the catalog, the order is the catalog's)
              const prev = g.items[i - 1];
              const divider = !!prev && (prev.section ?? 0) !== (it.section ?? 0);
              return (
                <Fragment key={it.id}>
                {divider && <hr className="cards-divider" />}
                <button disabled={it.disabled || unfit} title={why ? `${tx(it.name)} (${why})` : `${tx(it.name)}${it.subtitle ? ' · ' + tx(it.subtitle) : ''}`}
                  className={'card' + (selected ? ' selected' : '')}
                  onClick={() => p.onSelect(g.id, it.id)}>
                  <Ico name={it.icon} size={32} />
                  <span className="card-name">{tx(it.name)}</span>
                  {why && <span className="card-sub">{why}</span>}
                </button>
                {v && (
                  <div className="card-variant" role="group" aria-label={tx(v.label)}>
                    <span className="card-variant-label">{tx(v.label)}</span>
                    {v.choices.map((c) => (
                      <button key={c.id} className={'var-chip' + (choice?.id === c.id ? ' on' : '')} aria-pressed={choice?.id === c.id}
                        onClick={() => p.onVariant(g.id, v.key, c.id)}>{tx(c.name)}</button>
                    ))}
                  </div>
                )}
                </Fragment>
              );
            })}
          </div>
        </aside>
      )}
    </>
  );
}
