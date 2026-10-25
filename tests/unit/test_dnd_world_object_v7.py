"""Exact additive place-operation contract, with immutable predecessor proof."""
import copy
import pytest
from dungeonmind_dnd.application import world_object_vocabulary as vocab
from dungeonmind_dnd.domain.errors import DndVocabularyIntegrityError

def test_v7_adds_only_exact_npc_operation_and_keeps_old_pins():
    old=vocab.load_builtin_world_object_v6_vocabulary()
    new=vocab.load_builtin_world_object_v7_vocabulary()
    assert vocab.vocabulary_sha256(old)=='2c6e2a8547515f968a960fa5647c5ba28ce0978b8e4adb60befe55ef45666845'
    assert vocab.vocabulary_sha256(vocab.load_builtin_world_object_v5_vocabulary())=='f9fd5420e0ab3849224e0d58cf83dd432ca2e5da22ce661b25654406ec9c60d8'
    assert new.object_kinds==old.object_kinds
    assert new.predicates[:-1]==old.predicates
    term=new.predicates[-1]
    assert term.term=='dnd5e:operates'
    assert term.subject_kinds==['dnd5e:npc'] and term.object_kinds==['dnd5e:location']
    assert all(p.term!='dnd5e:operates' for p in old.predicates)
    ref=vocab.builtin_world_object_v7_vocabulary_ref()
    assert ref.vocabulary_revision=='world-object-v7'
    assert ref.catalog_sha256==vocab.vocabulary_sha256(new)
    assert vocab.builtin_world_object_v6_vocabulary_ref().catalog_sha256==vocab.vocabulary_sha256(old)

@pytest.mark.parametrize('change',[ 'revision','namespace','endpoint','profile'])
def test_v7_integrity_refusals(monkeypatch,change):
    original=vocab._load_json_resource
    def altered(directory,name,*,description):
        data=original(directory,name,description=description)
        if name=='world-object-v7.json':
            data=copy.deepcopy(data)
            if change=='revision':data['vocabulary_revision']='world-object-v8'
            if change=='namespace':data['predicates'][-1]['term']='unknown:operates'
            if change=='endpoint':data['predicates'][-1]['object_kinds']=['dnd5e:unknown']
            if change=='profile':data['semantic_profile']['descriptor_sha256']='0'*64
        return data
    monkeypatch.setattr(vocab,'_load_json_resource',altered)
    with pytest.raises(DndVocabularyIntegrityError):vocab.load_builtin_world_object_v7_vocabulary()
