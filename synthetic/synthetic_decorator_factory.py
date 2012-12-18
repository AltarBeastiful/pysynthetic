#-*- coding: utf-8 -*-
#
# Created on Dec 17, 2012
#
# @author: Younes JAAIDI
#
# $Id: $
#

from collections import OrderedDict
from contracts import contract
from synthetic.i_naming_convention import INamingConvention
from synthetic.synthetic_member import SyntheticMember
from synthetic.synthetic_meta_data import SyntheticMetaData
import inspect


class SyntheticDecoratorFactory:

    @contract
    def syntheticMemberDecorator(self,
                                 memberName : str,
                                 defaultValue,
                                 contract,
                                 readOnly : bool,
                                 namingConvention : INamingConvention,
                                 getterName : 'str|None',
                                 setterName : 'str|None',
                                 privateMemberName : 'str|None'):
        syntheticMember = SyntheticMember(memberName,
                                          defaultValue,
                                          contract,
                                          readOnly,
                                          getterName,
                                          setterName,
                                          privateMemberName)
        
        def decoratorFunction(cls):
            # Creating synthesization data if it does not exist.
            self._makeSyntheticDataIfNotExists(cls)
            
            # Inserting this member at the beginning of the member list of synthesization data attribute
            # because decorators are called in reversed order.
            cls.__syntheticMetaData__.insertSyntheticMemberAtBegin(syntheticMember)
            
            self._overrideConstructor(cls)
            self._makeGetter(cls, namingConvention, syntheticMember)
            self._makeSetter(cls, namingConvention, syntheticMember)
            return cls
        return decoratorFunction

    def syntheticConstructorDecorator(self):
        def decoratorFunction(cls):
            # Creating synthesization data if it does not exist.
            self._makeSyntheticDataIfNotExists(cls)
            
            # This will be used later to tell the new constructor to consume parameters to initialize members.
            cls.__syntheticMetaData__.setConsumeArguments(True)
            
            self._overrideConstructor(cls)
            return cls
        return decoratorFunction

    def _makeSyntheticDataIfNotExists(self, cls):
        if not hasattr(cls, '__syntheticMetaData__'):
            cls.__syntheticMetaData__ = SyntheticMetaData(originalConstructor = cls.__init__)

    def _overrideConstructor(self, cls):
        # Retrieving synthesized member list and original init method.
        originalConstructor = cls.__syntheticMetaData__.originalConstructor()
        syntheticMemberList = cls.__syntheticMetaData__.syntheticMemberList()
        doesConsumeArguments = cls.__syntheticMetaData__.doesConsumeArguments()
        
        def init(instance, *args, **kwargs):
            # Original constructor's expected args.
            originalConstructorExpectedArgList = []
            doesExpectVariadicArgs = False
            doesExpectKeywordedArgs = False
            
            if inspect.isfunction(originalConstructor):
                fullArgSpec = inspect.getfullargspec(originalConstructor)
                # originalConstructorExpectedArgList = expected args - self.
                originalConstructorExpectedArgList = fullArgSpec.args[1:]
                doesExpectVariadicArgs = (fullArgSpec.varargs is not None)
                doesExpectKeywordedArgs = (fullArgSpec.varkw is not None)
                   
            # Merge original constructor's args specification with member list and make an args dict.
            positionalArgumentKeyValueList = self._positionalArgumentKeyValueList(originalConstructorExpectedArgList,
                                                                                syntheticMemberList,
                                                                                args)

            # Set members values.
            for syntheticMember in syntheticMemberList:
                memberName = syntheticMember.memberName()
                
                # Default value.
                value = syntheticMember.defaultValue()

                # Constructor is synthesized.
                if doesConsumeArguments:
                    value = self._consumeArgument(memberName,
                                                  positionalArgumentKeyValueList,
                                                  kwargs,
                                                  value)

                # Initalizing member with a value.
                setattr(instance,
                        syntheticMember.privateMemberName(),
                        value)

            # Remove superfluous arguments that have been used for synthesization but are not expected by constructor.
            args, kwargs = self._filterArgsAndKwargs(originalConstructorExpectedArgList,
                                                   doesExpectVariadicArgs,
                                                   doesExpectKeywordedArgs,
                                                   syntheticMemberList,
                                                   positionalArgumentKeyValueList,
                                                   kwargs)
            # Call original constructor.
            originalConstructor(instance, *args, **kwargs)
        
        # Setting init method.
        cls.__init__ = init

    @contract
    def _positionalArgumentKeyValueList(self,
                                        originalConstructorExpectedArgList,
                                        syntheticMemberList : list,
                                        argTuple : tuple):
        """Transforms args tuple to a dictionary mapping argument names to values using original constructor
positional args specification, then it adds synthesized members at the end if they are not already present."""
        
        # First, the list of expected arguments is set to original constructor's arg spec. 
        expectedArgList = originalConstructorExpectedArgList.copy()
        
        # ... then we append members that are not already present.
        for syntheticMember in syntheticMemberList:
            memberName = syntheticMember.memberName()
            if memberName not in expectedArgList:
                expectedArgList.append(memberName)
        
        # Makes a list of tuples (argumentName, argumentValue) with each element of each list (expectedArgList, argTuple)
        # until the shortest list's end is reached.
        positionalArgumentKeyValueList = list(zip(expectedArgList, argTuple))
        
        # Add remanining arguments (those that are not expected by the original constructor).
        for argumentValue in argTuple[len(positionalArgumentKeyValueList):]:
            positionalArgumentKeyValueList.append((None, argumentValue))

        return positionalArgumentKeyValueList

    @contract
    def _consumeArgument(self,
                         memberName: str,
                         positionalArgumentKeyValueList: list,
                         kwargs: dict,
                         defaultValue):
        """Returns member's value from kwargs if found or from positionalArgumentKeyValueList if found
or default value otherwise."""
        # Warning: we use this dict to simplify the usage of the key-value tuple list but be aware that this will
        # merge superfluous arguments as they have the same key : None.
        positionalArgumentDict = dict(positionalArgumentKeyValueList)
     
        if memberName in kwargs:
            return kwargs[memberName]

        if memberName in positionalArgumentDict:
            return positionalArgumentDict[memberName]

        return defaultValue

    @contract
    def _filterArgsAndKwargs(self,
                           originalConstructorExpectedArgList : 'list(str)',
                           doesExpectVariadicArgs : bool,
                           doesExpectKeywordedArgs : bool,
                           syntheticMemberList : list,
                           positionalArgumentKeyValueList : list,
                           keywordedArgDict : dict):
        """Returns a tuple with variadic args and keyworded args after removing arguments that have been used to
synthesize members and that are not expected by the original constructor.
If original constructor accepts variadic args, all variadic args are forwarded.
If original constructor accepts keyworded args, all keyworded args are forwarded."""
        
        # List is initialized with all variadic arguments.
        positionalArgumentKeyValueList = positionalArgumentKeyValueList.copy()
        
        # Warning: we use this dict to simplify the usage of the key-value tuple list but be aware that this will
        # merge superfluous arguments as they have the same key : None.
        positionalArgumentDict = dict(positionalArgumentKeyValueList)
        
        # Dict is initialized with all keyworded arguments.
        keywordedArgDict = keywordedArgDict.copy()
        
        for syntheticMember in syntheticMemberList:
            argumentName = syntheticMember.memberName()
            
            # Argument is expected by the original constructor.
            if argumentName in originalConstructorExpectedArgList:
                continue

            # We filter args only if original constructor does not expected variadic args. 
            if not doesExpectVariadicArgs and argumentName in positionalArgumentDict:
                positionalArgumentKeyValueList = list(filter(lambda pair: pair[0] != argumentName,
                                                             positionalArgumentKeyValueList))

            # We filter args only if original constructor does not expected keyworded args. 
            if not doesExpectKeywordedArgs and argumentName in keywordedArgDict:
                del keywordedArgDict[argumentName]

        positionalArgumentTuple = tuple([value for _, value in positionalArgumentKeyValueList])
        return positionalArgumentTuple, keywordedArgDict

    def _makeGetter(self, cls, namingConvention, syntheticMember):
        def getter(instance):
            return getattr(instance, syntheticMember.privateMemberName())
        setattr(cls, self._getterName(namingConvention, syntheticMember), getter)
    
    def _makeSetter(self, cls, namingConvention, syntheticMember):
        # No setter if read only member.
        if syntheticMember.isReadOnly():
            return
        
        def setter(instance, value):
            setattr(instance, syntheticMember.privateMemberName(), value)
        setattr(cls, self._setterName(namingConvention, syntheticMember), setter)

    def _getterName(self, namingConvention, syntheticMember):
        getterName = syntheticMember.getterName()
        if getterName is None:
            getterName = namingConvention.getterName(syntheticMember.memberName())
        return getterName
    
    def _setterName(self, namingConvention, syntheticMember):
        setterName = syntheticMember.setterName()
        if setterName is None:
            setterName = namingConvention.setterName(syntheticMember.memberName())
        return setterName
