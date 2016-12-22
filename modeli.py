import sqlite3

con = sqlite3.connect('urnik.sqlite3')
con.row_factory = sqlite3.Row


def seznam_ucilnic(velikost=0):
    sql = '''
        SELECT id, oznaka, velikost, racunalniska
        FROM ucilnica
        WHERE velikost >= ?
        ORDER BY oznaka
    '''
    return list(con.execute(sql, [velikost]))


def seznam_oseb():
    sql = '''
        SELECT id, ime, priimek, email
        FROM oseba
        ORDER BY priimek, ime
    '''
    return list(con.execute(sql))


def seznam_letnikov():
    sql = '''
        SELECT id, smer, letnik, stevilo_studentov
        FROM letnik
        ORDER BY smer, letnik
    '''
    return list(con.execute(sql))


def oseba(oseba):
    sql = '''
        SELECT id, ime, priimek, email
        FROM oseba
        WHERE id = ?
    '''
    return con.execute(sql, [oseba]).fetchone()


def uredi_osebo(oseba, ime, priimek, email):
    sql = '''
        UPDATE oseba
        SET ime = ?, priimek = ?, email = ?
        WHERE id = ?
    '''
    con.execute(sql, [ime, priimek, email, oseba])
    con.commit()


def ucilnica(ucilnica):
    sql = '''
        SELECT id, oznaka, velikost, racunalniska
        FROM ucilnica
        WHERE id = ?
    '''
    return con.execute(sql, [ucilnica]).fetchone()


def uredi_ucilnico(ucilnica, oznaka, velikost, racunalniska):
    sql = '''
        UPDATE ucilnica
        SET oznaka = ?, velikost = ?, racunalniska = ?
        WHERE id = ?
    '''
    con.execute(sql, [oznaka, velikost, racunalniska, ucilnica])
    con.commit()


def urnik(srecanja):
    sql = '''
        SELECT srecanje.id,
               dan,
               ura,
               trajanje,
               tip,
               oseba.ime,
               oseba.priimek,
               ucilnica.oznaka
          FROM srecanje
               INNER JOIN
               oseba ON srecanje.ucitelj = oseba.id
               INNER JOIN
               ucilnica ON srecanje.ucilnica = ucilnica.id
         WHERE srecanje.id IN ({})
         ORDER BY dan,
                  ura;
    '''.format(','.join(str(srecanje['id']) for srecanje in srecanja))
    print(sql)
    return list(con.execute(sql))


def urnik_ucilnice(ucilnica):
    sql = '''
        SELECT id
          FROM srecanje
         WHERE ucilnica = ?;
    '''
    return urnik(con.execute(sql, [ucilnica]))


def urnik_osebe(oseba):
    sql = '''
        SELECT id
          FROM srecanje
         WHERE ucitelj = ?;
    '''
    return urnik(con.execute(sql, [oseba]))


def urnik_letnika(letnik):
    sql = '''
        SELECT id
          FROM srecanje
               INNER JOIN
               letnik_srecanje ON srecanje.id = letnik_srecanje.srecanje
         WHERE letnik_srecanje.letnik = ?;
    '''
    return urnik(con.execute(sql, [letnik]))


def prekrivanje_ucilnic():
    '''Vrne podatke o prekrivanju srečanj po učilnicah.

    Funkcija vrne slovar, ki trojici (ID učilnice, dan, ura)
    priredi seznam ID-jev srečanj, ki tam in takrat potekajo hkrati.
    '''
    sql = '''
    SELECT prvo.ucilnica AS ucilnica,
           prvo.dan AS dan,
           drugo.ura AS ura,
           prvo.id AS prvo,
           drugo.id AS drugo
      FROM srecanje AS prvo
           INNER JOIN
           srecanje AS drugo ON prvo.ucilnica = drugo.ucilnica AND 
                                prvo.dan = drugo.dan
     WHERE prvo.id != drugo.id AND 
           prvo.ura <= drugo.ura AND 
           drugo.ura < prvo.ura + prvo.trajanje
    '''
    prekrivanja = {}
    for ucilnica, dan, ura, prvo, drugo in con.execute(sql):
        prekrivanja_v_terminu = prekrivanja.get((ucilnica, dan, ura), [])
        prekrivanja_v_terminu.append(prvo)
        prekrivanja_v_terminu.append(drugo)
        prekrivanja[(ucilnica, dan, ura)] = prekrivanja_v_terminu
    return prekrivanja


def proste_ucilnice():
    '''Vrne podatke o vseh prostih učilnicah.

    Funkcija vrne slovar, ki paru (dan, ura) priredi seznam ID-jev
    učilnic, ki so takrat proste. Če prostih učilnic ni, se par (dan, ura)
    v slovarju ne pojavi.
    '''
    return {
        (1, 10): [6],
        (3, 8): [1, 2, 3]
    }
