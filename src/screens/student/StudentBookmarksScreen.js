import React,{useEffect,useState} from 'react';
import {Alert,Text,View} from 'react-native';
import {AppShell,Button,Card,Empty,ErrorState,Header,Loading} from '../../components/UI';
import {api} from '../../services/api';
import {colors} from '../../theme';

export default function StudentBookmarksScreen(){
 const [items,setItems]=useState(null),[error,setError]=useState('');
 const load=async()=>{try{setError('');setItems(api.listOf(await api.bookmarks()))}catch(e){setError(e.message)}};
 useEffect(()=>{load()},[]);
 const remove=async id=>{try{await api.deleteBookmark(id);load()}catch(e){Alert.alert('Bookmark',e.message)}};
 if(error)return <AppShell><Header title="Bookmarks"/><ErrorState title="Bookmarks could not load" message={error} onRetry={load}/></AppShell>;
 if(!items)return <AppShell><Loading label="Loading bookmarks…"/></AppShell>;
 return <AppShell><Header title="Bookmarks" subtitle="Save lessons and resources you want to revisit."/>
 {items.length===0?<Empty title="No bookmarks" message="Bookmark a lesson from a course to see it here."/>:items.map(b=><Card key={api.idOf(b)}><View style={{flexDirection:'row',alignItems:'center',gap:10}}><View style={{flex:1}}><Text style={{fontWeight:'900',color:colors.navy}}>{b.title||'Saved learning item'}</Text><Text style={{fontSize:12,color:colors.muted,marginTop:4}}>{b.item_type} · {b.item_id}</Text></View><Button title="Remove" variant="danger" onPress={()=>remove(api.idOf(b))}/></View></Card>)}
 </AppShell>;
}
