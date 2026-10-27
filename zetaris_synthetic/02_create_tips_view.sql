CREATE SCHEMASTORE VIEW goal_tips WITH CONTAINER little_jahsi_demo AS
SELECT 'speak' AS topic, 'Ask one clarifying question about the material during tomorrow class.' AS tip
UNION ALL
SELECT 'calm' AS topic, 'Take one slow breath before answering a difficult question tomorrow.' AS tip
UNION ALL
SELECT 'connect' AS topic, 'Say hello to one familiar person tomorrow.' AS tip
