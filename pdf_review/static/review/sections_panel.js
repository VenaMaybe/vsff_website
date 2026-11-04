import { LeftCard } from './left_card.js';

export class SectionsPanel extends LeftCard {
  constructor(opener, onVisibility, viewer) {
    super('Sections', { opener, viewer, onVisibility, className: 'sections-panel', stateKey:'sections' });
  }
}
