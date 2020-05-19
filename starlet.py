#!/usr/bin/env python3

import sys

new_exit_list = None  # Used for loop/exit function
nextLabel = 0  # Label counter
quadDict = {}  # A dict with key: Line number, and value: a quad(list)
tCounter = 1  # Token counter
lineno = 1  # Current line  number of input file.
token_captivated = ['program', 'endprogram', 'declare', 'if', 'then', 'else',
                    'endif', 'while', 'endwhile', 'dowhile', 'enddowhile', 'loop', 'endloop', 'exit',
                    'forcase', 'endforcase', 'incase', 'endincase', 'when', 'default', 'enddefault',
                    'function', 'endfunction', 'return', 'in', 'inout', 'inandout', 'and', 'or', 'not',
                    'input', 'print']
scopes_list = list()  # A list of scopes
loop_enabled = False
func_enabled = False
ret_enabled = False
asm_file = None
parlist = list()
lmain_flag = True

#########################################################
#                           LEX                         #
#########################################################


# State:    1-> words       3-> '<'     5-> ':'
#           2-> digits      4-> '>'     6-> '/'
def lex():
    buffer = []
    state = 0  # Initial FSM state (starting point)
    ok = -2  # Final State
    getback = False  # True if we need to reposition file pointer

    # Lexical analyzer's FSM implementation
    while state != ok:
        char = data.read(1)  # Reading one character at a time
        buffer.append(char)
        if state == 0:
            if char.isalpha():
                state = 1
            elif char.isdigit():
                state = 2
            elif char == '<':
                state = 3
            elif char == '>':
                state = 4
            elif char == ':':
                state = 5
            elif char == '/':
                state = 6
            elif char in ('+', '-', '*', '=', ',', ';', '(', ')', '[', ']'):
                state = ok
            elif char == '':
                state = ok
            elif char.isspace():
                state = 0
            else:
                print("(lex) invalid character: " + char)
                sys.exit()

        elif state == 1:
            if not char.isalnum():
                getback = True
                state = ok
        elif state == 2:
            if not char.isdigit():
                if char.isalpha():
                    error(" (lex) not valid integer: ")
                getback = True
                state = ok
        elif state == 3:
            if char != '=' and char != '>':
                getback = True
            state = ok
        elif state == 4:
            if char != '=':
                getback = True
            state = ok
        elif state == 5:
            if char != '=':
                getback = True
            state = ok
        elif state == 6:
            if char == '/':
                state = 7
            elif char == '*':
                state = 8
            else:
                getback = True
                state = ok
        elif state == 7:
            if char == '\n':
                del buffer[:]
                state = 0

        elif state == 8:

            if char == '*':
                state = 9
            elif char == '':
                print("No closing comment found")
                sys.exit()

        elif state == 9:

            if char == '/':
                del buffer[:]
                state = 0
            else:
                state = 8

        # Ignoring spaces and counting lines
        if char.isspace():
            if char == '\n':
                global lineno
                lineno += 1
            if len(buffer) != 0:
                del buffer[-1]
            getback = False

    # Repositioning file pointer
    if getback:
        data.seek(data.tell() - 1)
        del buffer[-1]

    ret = ''.join(buffer)

    # Checking if digit is out of bounds
    if ret.isdigit():
        if abs(int(ret)) > 32767:
            error("(lex) digit is out of bounds! ")

    # Emptying the buffer
    del buffer[:]

    # Returning the first 30 characters
    return ret[:30]


##################################################################
#                            SYNTAX                              #
##################################################################

def program():
    global token, program_name, scopes_list
    token = lex()

    if token == 'program':
        token = lex()
        if is_valid_id(token):
            program_name = name = token
            token = lex()
            # Creating and adding Scope to scopes_list(default nesting_level = 0)
            scopes_list.append(Scope())

            block(name)

            if token != 'endprogram':
                error("expected endprogram, found: ")

        else:
            error(" (program) expected an 'id' found: ")
    else:
        error("(program) expected 'program' found: ")


def block(name):
    declarations()
    subprograms()

    # Setting start_quad(LineNo of .int where the current function starts) for each Function(Entity) 
    start_quad = next_quad()
    if name != program_name:
        en = search_entity(name, 'FUNC')[0]
        en.set_start_quad(start_quad)

    gen_quad('begin_block', name)
    statements()

    if program_name == name:
        gen_quad('halt')
    else:
        # Update framelength
        f_entity = search_entity(name, 'FUNC')[0]
        f_entity.framelength = scopes_list[len(scopes_list) - 1].get_sp()

    gen_quad('end_block', name)

    # Printing Scopes and entities before deleting it
    print(scopes_list[-1])
    for en in scopes_list[-1].entities:
        print(en)
    print("--------------------------------------------")

    for i in range(start_quad, nextLabel):
        write_to_asm(quadDict[i], name, i)

    # Block is done, deleting Scope
    del scopes_list[-1]


def declarations():
    global token
    while token == 'declare':
        token = lex()
        varlist()
        if token != ';':
            error(" (declarations) expected ';' found: ")
        token = lex()


def varlist():
    global token

    if is_valid_id(token):

        # Adding (declarations)token as a Variable entity
        add_var_entity(token)

        token = lex()
        while token == ',':
            token = lex()
            if not is_valid_id(token):
                error(" (varlist) expected 'id', found: ")

            # Adding token as a Variable entity
            add_var_entity(token)
            token = lex()
    elif token != ';':
        error(" (varlist) not valid id: ")

    # Storing the declarations of the current scope to the previous (Enclosing scope)
    # if len(scopes_list) >= 2:
    #     scopes_list[-2].set_enclosing_scope(scopes_list[-1].entities)


def subprograms():
    global token, func_enabled

    while token == 'function':
        func_enabled = True
        token = lex()
        subprogram()


def subprogram():
    global token, func_enabled, ret_enabled

    if is_valid_id(token):
        name = token
        # Creating and adding new scope (nesting level depends on the length of our scopes_list)
        new_scope = Scope(scopes_list.__len__(), scopes_list[-1])

        scopes_list.append(new_scope)

        token = lex()

        # Adding Func entity
        scopes_list[-2].add_entity(Function(name, 0))

        funcbody(name)
        if token != 'endfunction':
            error(" (subprogram) expected endfuction, found: ")

        if not ret_enabled:
            error(" No return in function/")
        func_enabled = False
        ret_enabled = False
        token = lex()
    else:
        error("(subprogram) expected 'id', found: ")


def funcbody(name):
    formalpars(name)
    block(name)


def formalpars(name):
    global token

    if token == '(':
        token = lex()

        formalparlist(name)
        if token != ')':
            error(" (formalpars) expected ')', found: ")
    else:
        error(" (formalpars) expected '(', found: ")

    token = lex()


def formalparlist(name):
    global token
    if token != ')':
        formalparitem(name)
        while token == ',':
            token = lex()
            formalparitem(name)


def formalparitem(name):
    global token

    if token in ('in', 'inout', 'inandout'):
        par_mode = token
        token = lex()
        if is_valid_id(token):
            # Add Argument(in/inout/inandout) to func
            add_arg_to_func(par_mode, name)

            # Add Parameter(Entity) to Scope
            add_param_entity(token, par_mode)

            token = lex()
        else:
            error("(formalparitem) expected id, found: ")
    else:
        error("expected 'in'/'inout'/'inandout', found: ")


def statements():
    global token
    statement()

    while token == ';':
        token = lex()
        statement()


def statement():
    global token, loop_enabled, ret_enabled

    if token == 'if':
        token = lex()
        if_stat()

    elif token == 'while':
        token = lex()
        while_stat()

    elif token == 'dowhile':
        token = lex()
        do_while_stat()

    elif token == 'loop':
        loop_enabled = True
        token = lex()
        loop_stat()
    elif token == 'exit':
        token = lex()
        if loop_enabled:
            exit_stat()
        else:
            error(" 'exit' must be declared inside a loop ")
    elif token == 'forcase':
        token = lex()
        forcase_stat()
    elif token == 'incase':
        token = lex()
        incase_stat()
    elif token == 'return':
        ret_enabled = True
        token = lex()
        exp = expression()

        gen_quad('retv', exp, '_', '_')
    elif token == 'print':
        token = lex()
        exp = expression()
        gen_quad('out', exp)
    elif token == 'input':
        token = lex()
        id_place = input_stat()
        gen_quad('inp', id_place)
    elif is_valid_id(token):
        assignment_stat()


def assignment_stat():
    global token

    if token.isalnum():
        t1 = token

        if not exists(t1):
            error(' Not declared: ')

        token = lex()

        if token == ':=':
            op = token
            token = lex()

            if not exists(token) and not token.isdigit():
                error(' Not declared: ')

            exp = expression()

            gen_quad(op, exp, '_', t1)

        else:
            error("(assignment_stat) expected ':=' found ")


def if_stat():
    global token

    if token == '(':
        token = lex()
    else:
        error("(if_stat) expected '(' found: ")

    (b_true, b_false) = condition()

    if token == ')':
        token = lex()

        backpatch(b_true, next_quad())
    else:
        error("(if_stat) expected ')' found: ")

    if token == 'then':

        token = lex()
        statements()
        skip = make_list(next_quad())
        gen_quad('jump')
        backpatch(b_false, next_quad())
        elsepart()
        backpatch(skip, next_quad())

        if token != 'endif':
            error("(if_stat) expected 'endif' found ")

        token = lex()

    else:
        error("(if_stat) expected 'then' found ")


def elsepart():
    global token

    if token == 'else':
        token = lex()
        statements()


def while_stat():
    global token
    quad = next_quad()
    if token == '(':
        token = lex()
    else:
        error("(while_stat) expected '(' found: ")

    (b_true, b_false) = condition()

    if token == ')':
        token = lex()
    else:
        error("(while_stat) expected ')' found: ")
    backpatch(b_true, next_quad())
    statements()
    gen_quad('jump', '_', '_', str(quad))
    backpatch(b_false, next_quad())

    if token != 'endwhile':
        error(" (while_stat) expected 'endwhile', found: ")
    token = lex()


def do_while_stat():
    global token
    quad = next_quad()
    statements()

    if token == 'enddowhile':
        token = lex()

        if token == '(':
            token = lex()
        else:
            error("(do_while_stat) expected '(' found: ")

        (b_true, b_false) = condition()

        if token == ')':
            backpatch(b_true, quad)
            n_quad = next_quad()
            backpatch(b_false, n_quad)
            token = lex()
        else:
            error("(do_while_stat) expected ')' found: ")
    else:
        error(" (do_while_stat) expected 'enddowhile', found: ")


def loop_stat():
    global token, new_exit_list, loop_enabled
    quad = next_quad()
    statements()

    gen_quad('jump', '_', '_', str(quad))
    if token != 'endloop':
        error(" (loop_stat) expected 'endloop', found: ")

    loop_enabled = False
    token = lex()

    if new_exit_list is not None:
        backpatch(new_exit_list, next_quad())
        new_exit_list = None


def exit_stat():
    global token, new_exit_list
    new_exit_list = make_list(next_quad())
    gen_quad('jump')


def forcase_stat():
    global token
    flag_quad = next_quad()

    exit_list = empty_list()

    while token == 'when':
        token = lex()
        if token == '(':
            token = lex()
        else:
            error("(forcase_stat) expected '(' found: ")

        (b_true, b_false) = condition()

        backpatch(b_true, next_quad())

        if token == ')':
            token = lex()
        else:
            error("(forcase_stat) expected ')' found: ")

        if token != ':':
            error("(forcase_stat) expected ':', found: ")
        token = lex()
        statements()
        t = make_list(next_quad())
        gen_quad('jump')
        exit_list = merge(exit_list, t)
        backpatch(b_false, next_quad())

    if token != 'default':
        error("(forcase_stat) expecred 'default',found: ")
    token = lex()
    if token != ':':
        error("(forcase_stat) expected ':', found: ")
    token = lex()
    statements()
    gen_quad('jump', '_', '_', str(flag_quad))
    backpatch(exit_list, next_quad())
    if token != 'enddefault':
        error("(forcase_stat) expected 'enddefault',found: ")
    token = lex()

    if token != 'endforcase':
        error("(forcase_stat) expected 'endforcase',found: ")
    token = lex()


def incase_stat():
    global token
    t = new_temp()
    flag_quad = next_quad()
    gen_quad(':=', '0', '_', t)

    while token == 'when':
        token = lex()
        if token == '(':
            token = lex()
        else:
            error("(incase_stat) expected '(' found: ")

        (b_true, b_false) = condition()
        backpatch(b_true, next_quad())
        gen_quad(':=', '1', '_', t)

        if token == ')':
            token = lex()
        else:
            error("(incase_stat) expected ')' found: ")

        if token != ':':
            error("(incase_stat) expected ':', found: ")
        token = lex()
        statements()
        backpatch(b_false, next_quad())

    if token != 'endincase':
        error("(incase_stat) expected 'endincase',found: ")
    token = lex()
    gen_quad('=', '1', t, str(flag_quad))


def input_stat():
    global token

    if not is_valid_id(token):
        error(" (input_stat) expected an 'id', found: ")
    ret = token
    token = lex()
    return ret


def actualpars():
    global token

    if token == '(':
        token = lex()
        actualparlist()

        if token != ')':
            error(" (actualpars) expected ')', found: ")

        token = lex()
        return True


def actualparlist():
    global token

    actualparitem()

    while token == ',':
        token = lex()
        actualparitem()


def actualparitem():
    global token

    if token == 'in':
        token = lex()
        if not exists(token):
            error(' Not declared: ')
        exp = expression()
        gen_quad('par', exp, 'CV')
    elif token == 'inout':
        token = lex()
        if not exists(token):
            error(' Not declared: ')
        t1 = token
        if not is_valid_id(token):
            error("(actualparitem) expected 'id' found ")
        token = lex()
        gen_quad('par', t1, 'REF')
    elif token == 'inandout':
        token = lex()
        if not exists(token):
            error(' Not declared: ')
        t2 = token
        if not is_valid_id(token):
            error("(actualparitem) expected 'id' found ")
        token = lex()
        gen_quad('par', t2, 'RET')


def condition():
    global token

    (b_true, b_false) = boolterm()

    while token == 'or':
        backpatch(b_false, next_quad())
        token = lex()

        (c_true, c_false) = boolterm()
        b_true = merge(b_true, c_true)
        b_false = c_false
    return b_true, b_false


def boolterm():
    global token

    (b_true, b_false) = boolfactor()

    while token == 'and':
        backpatch(b_true, next_quad())
        token = lex()
        (c_true, c_false) = boolfactor()
        b_false = merge(b_false, c_false)
        b_true = c_true
    return b_true, b_false


def boolfactor():
    global token

    if token == 'not':
        token = lex()
        if token == '[':
            token = lex()

            ret = condition()

            if token != ']':
                error(" (boolfactor) expected ']', found: ")

            token = lex()
        else:
            error(" (boolfactor) expected '[', found: ")

    elif token == '[':
        token = lex()

        ret = condition()

        if token != ']':
            error(" (boolfactor) expected ']', found: ")

        token = lex()

    else:

        exp1 = expression()
        op = relational_oper()
        exp2 = expression()

        b_true = make_list(next_quad())
        gen_quad(op, exp1, exp2)
        b_false = make_list(next_quad())
        gen_quad('jump')
        ret = (b_true, b_false)
    return ret


def expression():
    global token

    op = optional_sign()
    t1 = term()

    while add_oper():
        op = token
        token = lex()

        if not exists(token) and not token.isdigit():
            error(' Not declared: ')

        t2 = term()

        tmp = new_temp()
        gen_quad(op, t1, t2, tmp)
        t1 = tmp
    return t1


def term():
    global token

    f1 = factor()
    while mul_oper():
        op = token
        token = lex()
        f2 = factor()

        tmp = new_temp()
        gen_quad(op, f1, f2, tmp)
        f1 = tmp
    return f1


def factor():
    global token

    if token.isdigit():
        ret = token
        token = lex()
    elif token == '(':
        token = lex()
        ret = expression()
        if token != ')':
            error("(factor) expected ')' found ")
        token = lex()

    elif is_valid_id(token):
        ret = token
        token = lex()
        tail = idtail()

        if tail is not None:
            new = new_temp()
            gen_quad('par', new, 'RET')
            gen_quad('call', ret)
            ret = new
    else:
        error("(factor) expected something found ")

    return ret


def idtail():
    global token

    if token == '(':
        return actualpars()


def optional_sign():
    global token

    if add_oper():
        token = lex()
        return token


def relational_oper():
    global token

    if token not in ('=', '<=', '>=', '>', '<', '<>'):
        error(" (relational_oper) expected a relation sign ")
    ret = token
    token = lex()
    return ret


def add_oper():
    global token
    if token == '+' or token == '-':
        # token = lex()      tin vgalame kai tin kaloume meta tin add_oper()
        return True
    return False


def mul_oper():
    global token

    if token == '*' or token == '/':
        # token = lex()      gia ton idio logo me ad_oper()
        return True
    return False


#################################################################
#                                                               #
#                              INT                              #
#                                                               #
#################################################################


def next_quad():
    return nextLabel


def gen_quad(op=None, x='_', y='_', z='_'):
    global nextLabel
    currentlabel = nextLabel
    nextLabel += 1
    quad = [op, x, y, z]
    quadDict[currentlabel] = quad


def new_temp():
    global tCounter

    temp = "T_" + str(tCounter)
    tCounter += 1

    # Create/Add new TempVariable to the current list of entities
    scopes_list[-1].add_entity(TempVariable(temp, scopes_list[-1].get_sp()))

    return temp


def empty_list():
    return list()


def make_list(x):
    newlist = list()
    newlist.append(x)
    return newlist


def merge(list1, list2):
    return list1 + list2


def backpatch(labellist, z):
    global quadDict

    for key in labellist:
        if key in quadDict:
            quadDict[key].pop()
            quadDict[key].append(z)


##################################################################
#                                                                #
#                          SYMBOL TABLE                          #
#                                                                #
##################################################################

class Entity:

    def __init__(self, name, entity_type):
        self.name = name
        self.entity_type = entity_type
        self.next = None

    def __str__(self):
        return self.name + ': ' + self.entity_type


# Variable inherits from Entity
class Variable(Entity):

    def __init__(self, name, offset=0):
        # Calling 'fathers' constructor and setting offset
        Entity.__init__(self, name, 'VAR')
        self.offset = offset

    def __str__(self):
        return Entity.__str__(self) + '\toffset: ' + str(self.offset)


# Function inherits from Entity
class Function(Entity):

    def __init__(self, name, ret_val, start_quad=-1):
        Entity.__init__(self, name, 'FUNC')
        self.ret_val = ret_val
        self.start_quad = start_quad
        self.arguments = list()
        self.framelength = -1

    def set_framelength(self, x):
        self.framelength = x

    def set_start_quad(self, x):
        self.start_quad = x

    def set_ret_val(self, x):
        self.ret_val = x

    def __str__(self):
        return Entity.__str__(self) + \
               ',\tStart_quad: ' + self.start_quad.__str__() + \
               ',\tFramelength:' + str(self.framelength) + \
               ',\tArgs:' + self.arguments.__str__()


# Parameter inherits from Entity
class Parameter(Entity):

    def __init__(self, name, par_mode, offset=0):
        Entity.__init__(self, name, 'PAR')
        if par_mode == 'in':
            self.par_mode = 'cv'
        elif par_mode == 'inout':
            self.par_mode = 'ref'
        else:
            self.par_mode = 'ret'
        self.offset = offset

    def __str__(self):
        return Entity.__str__(self) + ',\tpar_mode: ' + self.par_mode + ',\toffset: ' + str(self.offset)


# TempVariable inherits from Entity
class TempVariable(Entity):

    def __init__(self, name, offset=0):
        Entity.__init__(self, name, 'TMPVAR')
        self.offset = offset

    def __str__(self):
        return Entity.__str__(self) + '\toffset: ' + str(self.offset)


class Scope:

    def __init__(self, nesting_level=0, enclosing_scope=None):
        self.entities = list()
        self.nesting_level = nesting_level
        self.enclosing_scope = enclosing_scope
        self.sp = 12

    def get_sp(self):
        ret = self.sp
        self.sp += 4
        return ret

    # Adding entity to list
    def add_entity(self, ent):
        self.entities.append(ent)

    def set_enclosing_scope(self, x):
        self.enclosing_scope = x

    def __str__(self):
        return self.__repr__() + \
               '\nNesting lvl: ' + self.nesting_level.__repr__() + \
               '\nEnclosing Scope: ' + self.enclosing_scope.__repr__()


class Argument:

    # Initializing an Argument --> par_mode:(ret/cv/ref), pointer next_argument, default int type
    def __init__(self, par_mode, next_argument):
        self.par_mode = par_mode
        self.type = 'Int'
        self.next_argument = next_argument


# Adding arguments to function
def add_arg_to_func(par_mode, f_name):
    func_en = search_entity(f_name, 'FUNC')[0]
    if func_en is None:
        error(' No definition: ')

    func_en.arguments.append(par_mode)


# Adding A Var(Entity) to the current scope and
# checking if the given Var already exists in the current nesting level(as a Parameter etc.)
def add_var_entity(var_name):
    var_lvl = scopes_list[-1].nesting_level
    var_off = scopes_list[-1].get_sp()

    if not unique(var_name, 'VAR', var_lvl):
        error(' var not declared')

    if exists_as_param(var_name, var_lvl):
        error(' Symbol is already declared as a parameter: ')

    scopes_list[-1].add_entity(Variable(var_name, var_off))


# Adding a Parameter(Entity) to the current scope
def add_param_entity(par_name, par_mode):
    par_lvl = scopes_list[-1].nesting_level
    par_off = scopes_list[-1].get_sp()

    if not unique(par_name, 'PAR', par_lvl):
        error(' (unique)')

    scopes_list[-1].add_entity(Parameter(par_name, par_mode, par_off))


# Check if var entity already exists as a parameter
def exists_as_param(name, level):
    for entity in scopes_list[level].entities:
        if entity.entity_type == 'PAR' and entity.name == name:
            return True
    return False


def unique(name, entity_type, nesting_level):
    for i in range(len(scopes_list[nesting_level].entities)):
        for j in range(len(scopes_list[nesting_level].entities)):
            x = scopes_list[nesting_level].entities[i]
            y = scopes_list[nesting_level].entities[j]

            if x.name == y.name and x.entity_type == y.entity_type and x.name == name and x.entity_type == entity_type:
                return False
    return True


def exists(name):
    for scope in scopes_list:
        for entity in scope.entities:
            if name == entity.name:
                return True

    return False


# Searching(in scope_list) a specific entity by its given name and type 
# and returning the first one we find
def search_entity(name, entity_type):
    for scope in scopes_list:
        for entity in scope.entities:
            if entity.entity_type == entity_type and entity.name == name:
                return entity, scope.nesting_level


# search entity by name anapoda
def testing(name):
    global scopes_list

    scope = scopes_list[-1]
    while scope is not None:
        for entity in scope.entities:
            if entity.name == name:
                return entity, scope.nesting_level
        scope = scope.enclosing_scope

    return None

##################################################################
#                                                                #
#                          FINAL CODE                            #
#                                                                #
##################################################################


def gnvlcode(v):
    global asm_file, scopes_list

    en, lvl = testing(v)

    if en is None:
        print('Undeclared variable ' + v)
        sys.exit()

    if en.entity_type == 'FUNC':
        print('Undeclared variable ' + v)
        sys.exit()

    current_lvl = scopes_list[-1].nesting_level
    diff_of_lvl = current_lvl - lvl

    asm_file.write('\tlw $t0, -4($sp)\n')

    while diff_of_lvl > 1:
        asm_file.write('\tlw $t0, -4($t0)\n')
        diff_of_lvl -= 1

    asm_file.write('\tadd $t0, $t0, - %d\n' % en.offset)


# Data transfer (v) to register #tr
def loadvr(v, r):
    global asm_file, scopes_list

    if str(v).isdigit():
        asm_file.write('\tli $t%s, %s\n' % (r, v))
    else:
        en, lvl = testing(v)

        if en is None:
            print('Undeclared variable ' + v)
            sys.exit()

        current_lvl = scopes_list[-1].nesting_level

        if en.entity_type == 'VAR' and lvl == 0:
            asm_file.write('\tlw $t%s, -%d($s0)\n' % (r, en.offset))
        elif (en.entity_type == 'VAR' and lvl == current_lvl) or \
             (en.entity_type == 'PAR' and lvl == current_lvl and en.par_mode == 'cv') or \
             (en.entity_type == 'TMPVAR'):

            asm_file.write('\tlw $t%s, -%d($sp)\n' % (r, en.offset))
        elif en.entity_type == 'PAR' and lvl == current_lvl and en.par_mode == 'ref':
            asm_file.write('\tlw $t0, -%d($sp)\n' % en.offset)
            asm_file.write('\tlw $t%s, ($t0)\n' % r)
        elif (en.entity_type == 'VAR' and lvl < current_lvl) or \
             (en.entity_type == 'PAR' and lvl < current_lvl and en.par_mode == 'cv'):

            gnvlcode(v)
            asm_file.write('\tlw $t%s, ($t0)\n' % r)
        elif en.entity_type == 'PAR' and lvl < current_lvl and en.par_mode == 'ref':

            gnvlcode(v)
            asm_file.write('\tlw $t0, ($t0)\n')
            asm_file.write('\tlw $t%s, ($t0)\n' % r)
        else:

            print("ERROR: (loadvr) couldn't transfer data to register...: " + v)
            sys.exit()


# Transfer data from register ($tr) to memory (variable v)
def storerv(r, v):
    global asm_file,  scopes_list

    en, lvl = testing(v)

    if en is None:
        print('Undeclared variable ' + v)
        sys.exit()

    current_lvl = scopes_list[-1].nesting_level

    if en.entity_type == 'VAR' and lvl == 0:
        asm_file.write('\tsw $t%s, -%d($s0)\n' % (r, en.offset))
    elif (en.entity_type == 'VAR' and lvl == current_lvl) or \
            (en.entity_type == 'PAR' and lvl == current_lvl and en.par_mode == 'cv') or \
            (en.entity_type == 'TMPVAR'):

        asm_file.write('\tsw $t%s, -%d($sp)\n' % (r, en.offset))
    elif en.entity_type == 'PAR' and lvl == current_lvl and en.par_mode == 'ref':
        asm_file.write('\tlw $t0, -%d($sp)\n' % en.offset)
        asm_file.write('\tsw $t%s, ($t0)\n' % r)
    elif (en.entity_type == 'VAR' and lvl < current_lvl) or \
            (en.entity_type == 'PAR' and lvl < current_lvl and en.par_mode == 'cv'):

        gnvlcode(v)
        asm_file.write('\tsw $t%s, ($t0)\n' % r)
    elif en.entity_type == 'PAR' and lvl < current_lvl and en.par_mode == 'ref':

        gnvlcode(v)
        asm_file.write('\tlw $t0, ($t0)\n')
        asm_file.write('\tsw $t%s, ($t0)\n' % r)
    else:
        print("ERROR: (storerv) couldn't transfer data from register to memory: " + v)
        sys.exit()


def write_to_asm(quad, name, labelno):
    global asm_file, quadDict, program_name, parlist, lmain_flag

    if name == program_name and lmain_flag:
        asm_file.write('Lmain:\n')
        asm_file.write('\tadd $sp,$sp, %d\n' % scopes_list[0].sp)
        asm_file.write('\tmove $s0,$sp\n')
        lmain_flag = False

    asm_file.write('L_' + str(labelno) + ':\n')

    if quad[0] == 'jump':
        asm_file.write('\tj L_%s\n' % quad[3])
    elif quad[0] == ':=':
        loadvr(quad[1], '1')
        storerv('1', quad[3])
    elif quad[0] in ('=', '<>', '<', '<=', '>', '>='):
        loadvr(quad[1], '1')
        loadvr(quad[2], '2')
        if quad[0] == '=':
            relop = 'beq'
        elif quad[0] == '<>':
            relop = 'bne'
        elif quad[0] == '<':
            relop = 'blt'
        elif quad[0] == '<=':
            relop = 'ble'
        elif quad[0] == '>':
            relop = 'bgt'
        elif quad[0] == '>=':
            relop = 'bge'

        asm_file.write('\t%s $t1, $t2, L_%s\n' % (relop, quad[3]))
    elif quad[0] in ('+', '-', '*', '/'):
        loadvr(quad[1], '1')
        loadvr(quad[2], '2')

        if quad[0] == '+':
            op = 'add'
        elif quad[0] == '-':
            op = 'sub'
        elif quad[0] == '*':
            op = 'mul'
        elif quad[0] == '/':
            op = 'div'

        asm_file.write('\t%s $t1, $t1, $t2\n' % op)
        storerv('1', quad[3])
    elif quad[0] == 'out':
        asm_file.write('\tli $v0, 1\n')
        asm_file.write('\tli $a0, %s\n' % quad[3])
        asm_file.write('\tsyscall\n')
    elif quad[0] == 'in':
        asm_file.write('\tli $v0, 5\n')
        asm_file.write('\tsyscall\n')
    elif quad[0] == 'retv':

        loadvr(quad[1], '1')
        asm_file.write('\tlw $t0, -8($sp)\n')
        asm_file.write('\tsw $t1, ($t0)\n')

    elif quad[0] == 'par':

        if name == program_name:
            en_lvl = 0
            framelength = scopes_list[0].sp
        else:
            en, en_lvl = search_entity(name, 'FUNC')
            framelength = en.framelength

        if not parlist:
            asm_file.write('\tadd $fp, $sp, %d\n' % framelength)

        parlist.append(quad)
        par_offset = 12 + 4*parlist.index(quad)
        if quad[2] == 'CV':
            loadvr(quad[1], '0')
            asm_file.write('\tsw $t0, -%d($fp)\n' % par_offset)
        elif quad[2] == 'REF':
            var_en, var_lvl = testing(quad[1])

            if var_en is None:
                error('Undeclared variable')
            if en_lvl == var_lvl:
                if var_en.entity_type == 'VAR' or (var_en.entity_type == 'PAR' and var_en.par_mode == 'cv'):
                    asm_file.write('\tadd $t0, $sp, -%d\n' % var_en.offset)
                    asm_file.write('\tsw $t0, -%d($fp)\n' % par_offset)
                elif var_en.entity_type == 'PAR' and var_en.par_mode == 'ref':
                    asm_file.write('\t$t0,  -%d($sp)\n' % var_en.offset)
                    asm_file.write('\tsw $t0, -%d($fp)\n' % par_offset)
            else:
                if var_en.entity_type == 'VAR' or (var_en.entity_type == 'PAR' and var_en.par_mode == 'cv'):
                    gnvlcode(quad[1])
                    asm_file.write('\tsw $t0, -%d($fp)\n' % par_offset)
                elif var_en.entity_type == 'PAR' and var_en.par_mode == 'ref':
                    gnvlcode(quad[1])
                    asm_file.write('\tlw $t0, ($t0)\n')
                    asm_file.write('\tsw $t0, -%d($fp)\n' % par_offset)
        elif quad[2] == 'RET':
            var_en, var_lvl = testing(quad[1])

            if var_en is None:
                error('Undeclared variable')
            asm_file.write('\tadd $t0, $sp, -%d\n' % var_en.offset)
            asm_file.write('\tsw $t0, -8($fp)\n')

    elif quad[0] == 'call':

        if name == program_name:
            en_lvl = 0
            framelength = scopes_list[0].sp
        else:
            en, en_lvl = search_entity(name, 'FUNC')
            framelength = en.framelength

        cn, cn_lvl = search_entity(quad[1], 'FUNC')

        if cn is None:
            error('Function not declared')

        for i in range(len(cn.arguments)):
            if (cn.arguments[i] == 'in' and parlist[i][2] != 'CV') or \
               (cn.arguments[i] == 'inout' and parlist[i][2] != 'REF') or \
               (cn.arguments[i] == 'inandout' and parlist[i][2] != 'RET'):

                print("ERROR: False parameter types in a called function\n")
                sys.exit()

        parlist = list()

        if cn_lvl == en_lvl:
            asm_file.write('\tlw $t0, -4($sp)\n')
            asm_file.write('\tsw $t0, -4($fp)\n')
        else:
            asm_file.write('\tsw $sp, -4($fp)\n')

        asm_file.write('\tadd $sp, $sp, %d\n' % framelength)
        asm_file.write('\tjal L_%d\n' % cn.start_quad)
        asm_file.write('\tadd $sp, $sp, -%d\n' % framelength)
    elif quad[0] == 'begin_block':
        asm_file.write('\tsw $ra,($sp)\n')

    elif quad[0] == 'end_block':
        if name == program_name:
            asm_file.write('\n')
        else:
            asm_file.write('\tlw $ra,($sp)\n')
            asm_file.write('\tjr $ra\n')
    elif quad[0] == 'halt':
        asm_file.write('\tli $v0, 10\n')
        asm_file.write('\tsyscall\n')


##################################################################
#                                                                #
#                         Other Functions                        #
#                                                                #
##################################################################


# Checking if token is valid
def is_valid_id(tk):
    if tk not in token_captivated:
        if not tk.isdigit():
            if tk.isalnum():
                return True

    return False


# An error function, outputting the type of the syntax problem
def error(x):
    print("Line " + str(lineno))
    print("ERROR " + x + str(token))
    sys.exit()


# Open files
def open_files(input_filename, int_filename, c_filename, asm_filename):
    global data, int_file, c_file, asm_file

    try:
        data = open(input_filename, 'r')
        int_file = open(int_filename, 'w')
        c_file = open(c_filename, 'w')
        asm_file = open(asm_filename, 'w')
        asm_file.write('L:\n\tj Lmain\n')

    except (FileNotFoundError, IOError):
        print("Couldn't read file, or file doesn't exist!")
        sys.exit()


def write_int_to_file():

    for key in quadDict:
        int_file.write(str(key) + ': ' + str(quadDict[key][0]) + ',' + str(quadDict[key][1]) + ',' + str(
            quadDict[key][2]) + ',' + str(quadDict[key][3]) + '\n')


def write_to_c():
    global quadDict, c_file

    c_file.write('#include <stdio.h>\n\n')
    c_file.write('int main()\n{\n')

    for key in quadDict:
        info = to_c(key)

        semi = ';' if info is not '' else '\t'

        c_file.write(
            '\tL_' + str(key) + ': ' + str(info) + semi + '\t//' + str(key) + ': ' + str(quadDict[key][0]) + ',' + str(
                quadDict[key][1]) + ',' + str(quadDict[key][2]) + ',' + str(quadDict[key][3]) + '\n')

    c_file.write('}')


# Function to create C syntax based on quadDict
def to_c(key):
    global quadDict
    first = str(quadDict[key][0])
    second = str(quadDict[key][1])
    third = str(quadDict[key][2])
    fourth = str(quadDict[key][3])

    if first in ('begin_block', 'end_block'):
        return ''
    elif first == ':=':
        return fourth + '=' + second
    elif first in ('+', '-', '*', '/'):
        return fourth + '=' + second + first + third
    elif first in ('=', '<>', '<', '<=', '>', '>='):
        assignment = first
        if first == '=':
            assignment = '=='
        elif first == '<>':
            assignment = '!='

        return 'if (' + second + assignment + third + ') goto L_' + fourth
    elif first == 'jump':
        return 'goto L_' + fourth
    elif first == 'halt':
        return 'return 0'
    elif first == 'out':
        return 'printf("%d\\n", ' + second + ')'

    return ''


def main():
    # Checking if file is passed
    if len(sys.argv) < 2:
        print("Please pass a file to be executed")
        sys.exit()

    # Getting file name
    filename = sys.argv[1][:-4]
    int_filename = filename + '.int'
    c_filename = filename + '.c'
    asm_filename = filename + '.asm'

    open_files(sys.argv[1], int_filename, c_filename, asm_filename)
    program()

    write_int_to_file()
    write_to_c()

    # Closing files
    data.close()
    int_file.close()
    c_file.close()
    asm_file.close()

    print("Successful!\nFiles:\n\t" + int_filename + ",\n\t" + c_filename + ',\n\t' + asm_filename +
          "\nwere created in your directory.")


if __name__ == "__main__":
    main()
