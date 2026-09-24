from drellion.project import ProjectState
from drellion.studio_model import add_clip,add_track,duplicate_clip,move_clip,set_fades,split_clip,trim_clip

def test_nondestructive_studio_clip_operations(tmp_path):
    project=ProjectState.create(tmp_path,"Song"); t1=add_track(project,"Vocal"); t2=add_track(project,"Music"); c=add_clip(project,t1.id,"vocal.wav","Verse",duration_seconds=20); trim_clip(project,c.id,2,12); left,right=split_clip(project,c.id,5); assert left.duration_seconds==5; assert right.source_offset_seconds==7; duplicate=duplicate_clip(project,right.id); move_clip(project,duplicate.id,10,t2.id); set_fades(project,duplicate.id,0.2,0.4,0.1); assert any(x.id==duplicate.id for x in t2.clips); assert duplicate.fade_out_seconds==0.4
