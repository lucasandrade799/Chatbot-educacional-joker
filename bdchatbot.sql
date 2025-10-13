-- ######################################################################
-- 1. CRIAÇÃO DAS TABELAS
-- ######################################################################

-- TABELA ALUNOS
CREATE TABLE Alunos (
    id_aluno INT PRIMARY KEY AUTO_INCREMENT,
    RA VARCHAR(10) NOT NULL UNIQUE,
    Nome_Completo VARCHAR(100) NOT NULL
);

-- TABELA DISCIPLINAS
CREATE TABLE Disciplinas (
    id_disciplina INT PRIMARY KEY AUTO_INCREMENT,
    Nome_Disciplina VARCHAR(100) NOT NULL,
    Semestre INT NOT NULL,
    UNIQUE (Nome_Disciplina, Semestre)
);

-- TABELA HISTORICO_ACADEMICO
CREATE TABLE Historico_Academico (
    id_registro INT PRIMARY KEY AUTO_INCREMENT,
    
    fk_id_aluno INT NOT NULL,
    fk_id_disciplina INT NOT NULL,
    
    Nota DECIMAL(4, 2) DEFAULT 0.00,
    Faltas INT DEFAULT 0,
    
    Estudos_Disciplinares_Concluido BOOLEAN DEFAULT FALSE,
    AVAS_Concluido BOOLEAN DEFAULT FALSE,
    
    FOREIGN KEY (fk_id_aluno) REFERENCES Alunos(id_aluno),
    FOREIGN KEY (fk_id_disciplina) REFERENCES Disciplinas(id_disciplina),
    UNIQUE (fk_id_aluno, fk_id_disciplina)
);

-- ######################################################################
-- 2. POPULANDO A TABELA DISCIPLINAS
-- ######################################################################

-- MATÉRIAS DO 1º SEMESTRE
INSERT INTO Disciplinas (Nome_Disciplina, Semestre) VALUES
('Introdução à Programação', 1),
('Lógica de Computação', 1),
('Fundamentos de Sistemas', 1),
('Português e Redação', 1);

-- MATÉRIAS DO 2º SEMESTRE
INSERT INTO Disciplinas (Nome_Disciplina, Semestre) VALUES
('Estruturas de Dados', 2),
('Banco de Dados I', 2),
('Arquitetura de Computadores', 2),
('Ética e Cidadania', 2);


-- ######################################################################
-- 3. POPULANDO A TABELA ALUNOS
-- ######################################################################

INSERT INTO Alunos (RA, Nome_Completo) VALUES
('R3487E5', 'Matheus de Assis Alves'),
('R6738H5', 'Matheus Balzi da Silva'),
('R818888', 'Lucas Gabriel da Silva Gardezan'),
('H755247', 'Matheus Henrique Castro de Oliveira'),
('R848140', 'Thainanda Alves Monteiro'),
('820793', 'Lucas da Silva Andrade');


-- ######################################################################
-- 4. REGISTRO DO HISTÓRICO ACADÊMICO (1º SEMESTRE)
-- ######################################################################

INSERT INTO Historico_Academico (
    fk_id_aluno, fk_id_disciplina, Nota, Faltas, Estudos_Disciplinares_Concluido, AVAS_Concluido
) VALUES
-- Matheus de Assis Alves (RA: R3487E5) - 1º Semestre
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Introdução à Programação' AND Semestre = 1), 8.5, 2, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Lógica de Computação' AND Semestre = 1), 7.0, 0, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Fundamentos de Sistemas' AND Semestre = 1), 9.2, 1, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Português e Redação' AND Semestre = 1), 6.5, 4, FALSE, TRUE),

-- Matheus Balzi da Silva (RA: R6738H5) - 1º Semestre
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Introdução à Programação' AND Semestre = 1), 5.5, 8, TRUE, FALSE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Lógica de Computação' AND Semestre = 1), 7.8, 1, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Fundamentos de Sistemas' AND Semestre = 1), 8.0, 0, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Português e Redação' AND Semestre = 1), 9.0, 3, TRUE, TRUE),

-- Lucas Gabriel da Silva Gardezan (RA: R818888) - 1º Semestre
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Introdução à Programação' AND Semestre = 1), 9.5, 0, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Lógica de Computação' AND Semestre = 1), 8.9, 0, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Fundamentos de Sistemas' AND Semestre = 1), 9.8, 0, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Português e Redação' AND Semestre = 1), 9.1, 0, TRUE, TRUE),

-- Matheus Henrique Castro de Oliveira (RA: H755247) - 1º Semestre
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Introdução à Programação' AND Semestre = 1), 6.0, 5, FALSE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Lógica de Computação' AND Semestre = 1), 5.5, 7, FALSE, FALSE),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Fundamentos de Sistemas' AND Semestre = 1), 7.2, 2, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Português e Redação' AND Semestre = 1), 8.5, 1, TRUE, TRUE),

-- Thainanda Alves Monteiro (RA: R848140) - 1º Semestre
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Introdução à Programação' AND Semestre = 1), 9.8, 0, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Lógica de Computação' AND Semestre = 1), 9.5, 0, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Fundamentos de Sistemas' AND Semestre = 1), 8.0, 1, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Português e Redação' AND Semestre = 1), 7.9, 0, TRUE, TRUE),

-- Lucas da Silva Andrade (RA: 820793) - 1º Semestre
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Introdução à Programação' AND Semestre = 1), 7.7, 3, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Lógica de Computação' AND Semestre = 1), 6.9, 4, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Fundamentos de Sistemas' AND Semestre = 1), 8.8, 1, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Português e Redação' AND Semestre = 1), 7.5, 2, TRUE, TRUE);

-- ######################################################################
-- 5. REGISTRO DO HISTÓRICO ACADÊMICO (2º SEMESTRE)
-- ######################################################################

INSERT INTO Historico_Academico (
    fk_id_aluno, fk_id_disciplina, Nota, Faltas, Estudos_Disciplinares_Concluido, AVAS_Concluido
) VALUES
-- Matheus de Assis Alves (RA: R3487E5) - 2º Semestre
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Estruturas de Dados' AND Semestre = 2), 7.5, 3, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Banco de Dados I' AND Semestre = 2), 8.8, 1, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Arquitetura de Computadores' AND Semestre = 2), 6.9, 5, TRUE, FALSE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R3487E5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Ética e Cidadania' AND Semestre = 2), 9.5, 0, TRUE, TRUE),

-- Matheus Balzi da Silva (RA: R6738H5) - 2º Semestre
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Estruturas de Dados' AND Semestre = 2), 6.0, 7, FALSE, FALSE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Banco de Dados I' AND Semestre = 2), 7.2, 4, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Arquitetura de Computadores' AND Semestre = 2), 8.5, 2, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R6738H5'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Ética e Cidadania' AND Semestre = 2), 5.0, 9, FALSE, TRUE),

-- Lucas Gabriel da Silva Gardezan (RA: R818888) - 2º Semestre
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Estruturas de Dados' AND Semestre = 2), 10.0, 0, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Banco de Dados I' AND Semestre = 2), 9.5, 0, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Arquitetura de Computadores' AND Semestre = 2), 9.9, 0, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R818888'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Ética e Cidadania' AND Semestre = 2), 9.0, 0, TRUE, TRUE),

-- Matheus Henrique Castro de Oliveira (RA: H755247) - 2º Semestre
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Estruturas de Dados' AND Semestre = 2), 5.5, 8, FALSE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Banco de Dados I' AND Semestre = 2), 6.5, 5, TRUE, FALSE),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Arquitetura de Computadores' AND Semestre = 2), 7.8, 3, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'H755247'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Ética e Cidadania' AND Semestre = 2), 8.0, 1, TRUE, TRUE),

-- Thainanda Alves Monteiro (RA: R848140) - 2º Semestre
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Estruturas de Dados' AND Semestre = 2), 9.0, 1, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Banco de Dados I' AND Semestre = 2), 8.5, 0, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Arquitetura de Computadores' AND Semestre = 2), 7.5, 2, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = 'R848140'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Ética e Cidadania' AND Semestre = 2), 9.3, 0, TRUE, TRUE),

-- Lucas da Silva Andrade (RA: 820793) - 2º Semestre
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Estruturas de Dados' AND Semestre = 2), 6.8, 5, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Banco de Dados I' AND Semestre = 2), 7.0, 3, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Arquitetura de Computadores' AND Semestre = 2), 8.2, 1, TRUE, TRUE),
((SELECT id_aluno FROM Alunos WHERE RA = '820793'), (SELECT id_disciplina FROM Disciplinas WHERE Nome_Disciplina = 'Ética e Cidadania' AND Semestre = 2), 7.9, 2, TRUE, TRUE);