-- Tableau 10 categorical palette, in its published order.
-- Source: https://d3js.org/d3-scale-chromatic/categorical#schemeTableau10
-- Exact values: https://github.com/d3/d3-scale-chromatic/blob/main/src/categorical/Tableau10.js
INSERT INTO review_palette(color) VALUES
('#4e79a7'),('#f28e2c'),('#e15759'),('#76b7b2'),('#59a14f'),
('#edc949'),('#af7aa1'),('#ff9da7'),('#9c755f'),('#bab0ab');

-- Preserve each user's approximate chosen hue, never their identity/history.
UPDATE users SET review_color = CASE review_color
    WHEN '#c66b54' THEN '#e15759'
    WHEN '#bc7651' THEN '#f28e2c'
    WHEN '#ad8042' THEN '#f28e2c'
    WHEN '#998b42' THEN '#edc949'
    WHEN '#7f9348' THEN '#59a14f'
    WHEN '#659a54' THEN '#59a14f'
    WHEN '#4f9b70' THEN '#59a14f'
    WHEN '#429987' THEN '#76b7b2'
    WHEN '#40959a' THEN '#76b7b2'
    WHEN '#488da9' THEN '#4e79a7'
    WHEN '#5682bb' THEN '#4e79a7'
    WHEN '#6c78bf' THEN '#4e79a7'
    WHEN '#8570bd' THEN '#af7aa1'
    WHEN '#9b6bb1' THEN '#af7aa1'
    WHEN '#b0669b' THEN '#af7aa1'
    WHEN '#be6682' THEN '#ff9da7'
    WHEN '#b77e6e' THEN '#9c755f'
    WHEN '#a18d68' THEN '#9c755f'
    WHEN '#87976c' THEN '#59a14f'
    WHEN '#6b9b85' THEN '#76b7b2'
    WHEN '#6899a5' THEN '#76b7b2'
    WHEN '#7c8db3' THEN '#4e79a7'
    WHEN '#9983b3' THEN '#af7aa1'
    WHEN '#b27f9b' THEN '#ff9da7'
    ELSE review_color END;

DELETE FROM review_palette WHERE color NOT IN (
    '#4e79a7','#f28e2c','#e15759','#76b7b2','#59a14f',
    '#edc949','#af7aa1','#ff9da7','#9c755f','#bab0ab'
);
