$(function(){
    function g(){
      $.ajax({
        url:'/generate',
        method:'GET',
        success:function(r){
          var e=r.expression
          $("#code").text(e)
          if($("#code").hasClass("nocode")){
            $("#code").removeClass("nocode")
            $("#code").addClass("code")
          }
        }
      })
    }
    setInterval(g,2500)
    $("#check").click(function(){
      var u=$(".input").val()
      $.ajax({
        url:'/verify',
        method:'POST',
        contentType:'application/json',
        data:JSON.stringify({user_input:u}),
        success:function(r){
          if(r.flag){alert("恭喜你，答案正确！Flag: "+r.flag)}
        },
        error:function(x){
          if(x.responseJSON&&x.responseJSON.error){alert(x.responseJSON.error)}
          else{alert("验证失败，请重试！")}
        }
      })
    })
  })
  